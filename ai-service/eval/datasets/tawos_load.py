"""One-pass streaming loader: TAWOS.sql (mysqldump, 4.3GB) -> local SQLite.

Reads the dump exactly once, line by line (never loads the whole file into
memory), and keeps only the six tables the ProjectSnapshot mapping needs —
Project, User, Sprint, Issue, Issue_Link, Comment. Large free-text columns
(Description, Comment body, Change_Log) are dropped at parse time since
nothing downstream reads them; that's most of the dump's bulk.

Run: python -m eval.datasets.tawos_load
"""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

from eval.datasets.mysqldump_parser import iter_rows, table_of

RAW_SQL_PATH = Path(__file__).parent / "raw" / "TAWOS.sql"
DB_PATH = Path(__file__).parent / "tawos.db"

SCHEMA = """
CREATE TABLE project (
    id INTEGER PRIMARY KEY,
    project_key TEXT,
    name TEXT,
    repository_id INTEGER
);
CREATE TABLE user (
    id INTEGER PRIMARY KEY,
    project_id INTEGER
);
CREATE TABLE sprint (
    id INTEGER PRIMARY KEY,
    jira_id INTEGER,
    name TEXT,
    state TEXT,
    start_date TEXT,
    end_date TEXT,
    activated_date TEXT,
    complete_date TEXT,
    project_id INTEGER
);
CREATE TABLE issue (
    id INTEGER PRIMARY KEY,
    issue_key TEXT,
    type TEXT,
    priority TEXT,
    status TEXT,
    resolution TEXT,
    creation_date TEXT,
    resolution_date TEXT,
    story_point REAL,
    creator_id INTEGER,
    reporter_id INTEGER,
    assignee_id INTEGER,
    project_id INTEGER,
    sprint_id INTEGER
);
CREATE TABLE issue_link (
    id INTEGER PRIMARY KEY,
    issue_id INTEGER,
    name TEXT,
    direction TEXT,
    target_issue_id INTEGER
);
CREATE TABLE comment (
    id INTEGER PRIMARY KEY,
    creation_date TEXT,
    author_id INTEGER,
    issue_id INTEGER
);
CREATE INDEX idx_issue_project ON issue(project_id);
CREATE INDEX idx_issue_sprint ON issue(sprint_id);
CREATE INDEX idx_link_issue ON issue_link(issue_id);
CREATE INDEX idx_comment_issue ON comment(issue_id);
"""

# Schema-order column indices for the fields we keep, per source table.
# (Full Issue row is 30 columns wide — see TAWOS_schema.sql — most dropped.)
ISSUE_COLS = [0, 2, 8, 9, 10, 11, 12, 14, 16, 25, 26, 27, 28, 29]
ISSUE_LINK_COLS = [0, 1, 2, 4, 5]
COMMENT_COLS = [0, 4, 5, 6]  # id, creation_date, author_id, issue_id
PROJECT_COLS = [0, 1, 2, 7]
USER_COLS = [0, 1]
SPRINT_COLS = [0, 1, 2, 3, 4, 5, 6, 7, 8]

TABLE_SPECS = {
    "Project": ("project", PROJECT_COLS, 4),
    "User": ("user", USER_COLS, 2),
    "Sprint": ("sprint", SPRINT_COLS, 9),
    "Issue": ("issue", ISSUE_COLS, 14),
    "Issue_Link": ("issue_link", ISSUE_LINK_COLS, 5),
    "Comment": ("comment", COMMENT_COLS, 4),
}


def main():
    if not RAW_SQL_PATH.exists():
        print(f"missing {RAW_SQL_PATH} — download and unzip TAWOS.sql.zip first", file=sys.stderr)
        sys.exit(1)

    DB_PATH.unlink(missing_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)

    placeholders = {name: ",".join("?" * n) for name, (_, _, n) in TABLE_SPECS.items()}
    inserts = {
        name: f"INSERT INTO {sql_table} VALUES ({placeholders[name]})"
        for name, (sql_table, _, _) in TABLE_SPECS.items()
    }

    counts = {name: 0 for name in TABLE_SPECS}
    start = time.time()
    batch: dict[str, list] = {name: [] for name in TABLE_SPECS}
    BATCH_SIZE = 20_000

    def flush(name: str):
        if batch[name]:
            conn.executemany(inserts[name], batch[name])
            batch[name].clear()

    with open(RAW_SQL_PATH, "rb") as f:
        for lineno, line in enumerate(f, 1):
            table = table_of(line)
            if table not in TABLE_SPECS:
                continue
            sql_table, cols, _ = TABLE_SPECS[table]
            for row in iter_rows(line):
                batch[table].append(tuple(row[i] for i in cols))
                counts[table] += 1
            if len(batch[table]) >= BATCH_SIZE:
                flush(table)
            if lineno % 200 == 0:
                print(f"\rline {lineno:>7}  " + "  ".join(f"{k}={v}" for k, v in counts.items()),
                      end="", file=sys.stderr)

    for name in TABLE_SPECS:
        flush(name)
    conn.commit()

    elapsed = time.time() - start
    print(f"\ndone in {elapsed:.1f}s", file=sys.stderr)
    for name, n in counts.items():
        print(f"  {name}: {n} rows", file=sys.stderr)
    conn.close()


if __name__ == "__main__":
    main()
