"""Extract one real TAWOS sprint into a small, self-contained JSON fixture.

tawos.db (built by tawos_load.py) keeps only the numeric/categorical columns
the evaluation needs, so it has no issue titles or comment text. A live demo
of real data should show what the engineers actually wrote, so this re-reads
the raw dump for just one sprint's issues and comments and writes them, plus
the structural fields from tawos.db, to a fixture small enough to commit.

The fixture lets the demo importer (backend/app/scripts/import_real_sprint.py)
run without the 4.3 GB dump. TAWOS is Apache-2.0; the fixture carries the
required citation.

Run (needs raw/TAWOS.sql and tawos.db; streams the dump once, several minutes):
    python -m eval.datasets.extract_sprint_fixture 379 ../backend/app/scripts/fixtures/mesos_sprint_74.json
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from eval.datasets.mysqldump_parser import iter_rows, table_of

HERE = Path(__file__).parent
RAW_SQL_PATH = HERE / "raw" / "TAWOS.sql"
DB_PATH = HERE / "tawos.db"

# Schema-order indices (see TAWOS_schema.sql).
ISSUE_ID, ISSUE_TITLE, ISSUE_DESC_TEXT = 0, 4, 6
COMMENT_ID, COMMENT_TEXT, COMMENT_DATE, COMMENT_AUTHOR, COMMENT_ISSUE = 0, 2, 4, 5, 6

CITATION = ("Tawosi, V., Al-Subaihin, A., Moussa, R., & Sarro, F. A Versatile Dataset of "
            "Agile Open Source Software Projects. MSR 2022. doi:10.1145/3524842.3528029 "
            "(Apache License 2.0)")


def _int(v):
    return int(v) if v is not None else None


def main(sprint_id: int, out_path: Path) -> None:
    conn = sqlite3.connect(DB_PATH)
    sprint = conn.execute(
        "select s.id, s.name, s.start_date, s.end_date, p.project_key, p.name "
        "from sprint s join project p on p.id = s.project_id where s.id = ?", (sprint_id,)
    ).fetchone()
    if not sprint:
        raise SystemExit(f"sprint {sprint_id} not found in tawos.db")

    issues = {
        r[0]: {
            "tawos_id": r[0], "key": r[1], "type": r[2], "priority": r[3], "status": r[4],
            "resolution": r[5], "created": r[6], "resolved": r[7], "story_points": r[8],
            "assignee": r[9], "reporter": r[10], "title": None, "description": None,
        }
        for r in conn.execute(
            "select id, issue_key, type, priority, status, resolution, creation_date, "
            "resolution_date, story_point, assignee_id, reporter_id from issue where sprint_id = ?",
            (sprint_id,),
        )
    }
    ids = list(issues)
    q = ",".join("?" * len(ids))
    links = [
        {"from": r[0], "type": r[1], "direction": r[2], "to": r[3]}
        for r in conn.execute(
            f"select issue_id, name, direction, target_issue_id from issue_link "
            f"where issue_id in ({q}) and target_issue_id in ({q})", ids + ids)
    ]

    comments = []
    wanted = set(ids)
    with open(RAW_SQL_PATH, "rb") as f:
        for line in f:
            table = table_of(line)
            if table == "Issue":
                for row in iter_rows(line):
                    iid = _int(row[ISSUE_ID])
                    if iid in wanted:
                        issues[iid]["title"] = row[ISSUE_TITLE]
                        desc = row[ISSUE_DESC_TEXT] or ""
                        issues[iid]["description"] = desc[:1500]
            elif table == "Comment":
                for row in iter_rows(line):
                    if _int(row[COMMENT_ISSUE]) in wanted:
                        comments.append({
                            "tawos_id": _int(row[COMMENT_ID]),
                            "issue": _int(row[COMMENT_ISSUE]),
                            "author": _int(row[COMMENT_AUTHOR]),
                            "created": row[COMMENT_DATE],
                            "text": (row[COMMENT_TEXT] or "")[:1500],
                        })

    fixture = {
        "source": "TAWOS", "citation": CITATION,
        "project": {"key": sprint[4], "name": sprint[5]},
        "sprint": {"tawos_id": sprint[0], "name": sprint[1], "start": sprint[2], "end": sprint[3]},
        "issues": sorted(issues.values(), key=lambda i: i["key"]),
        "links": links,
        "comments": sorted(comments, key=lambda c: c["created"] or ""),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(fixture, indent=1, ensure_ascii=False), encoding="utf-8")
    missing = [i["key"] for i in issues.values() if not i["title"]]
    print(f"wrote {out_path}: {len(issues)} issues, {len(links)} links, {len(comments)} comments; "
          f"titles missing for {len(missing)}")


if __name__ == "__main__":
    main(int(sys.argv[1]), Path(sys.argv[2]))
