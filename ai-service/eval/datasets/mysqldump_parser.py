"""A small, careful parser for mysqldump's extended-INSERT format.

Not a general SQL parser — deliberately narrow, matching exactly what
mysqldump emits: `INSERT INTO \`Table\` VALUES (row),(row),...;` where each
value is a MySQL-quoted string (backslash-escaped), a bare number, or `NULL`.
Hand-rolled rather than pulling in a general SQL library because the format
is small, fixed, and worth verifying by hand for a dataset headed into a
published metric — a mis-parsed row would be a silent data-correctness bug,
not a crash.

Verified directly against real TAWOS.sql content before being trusted here:
backslash-escaped single quotes, unquoted NULL, unquoted numerics.
"""

from __future__ import annotations

from typing import Iterator

INSERT_PREFIX = b"INSERT INTO `"


def table_of(line: bytes) -> str | None:
    """Return the target table name if this line starts an INSERT, else None."""
    if not line.startswith(INSERT_PREFIX):
        return None
    end = line.index(b"`", len(INSERT_PREFIX))
    return line[len(INSERT_PREFIX):end].decode("utf-8")


def iter_rows(line: bytes) -> Iterator[list]:
    """Yield each row (as a list of Python values) from one INSERT line.

    Assumes `line` is a complete statement ending in `;` — mysqldump's
    extended-insert writes one full statement per line, which is what every
    line in TAWOS.sql observed here does (confirmed by direct inspection).
    """
    values_kw = b" VALUES "
    start = line.index(values_kw) + len(values_kw)
    s = line[start:].rstrip(b"\n").rstrip(b";")
    text = s.decode("utf-8")

    i, n = 0, len(text)
    while i < n:
        while i < n and text[i] in " ,":
            i += 1
        if i >= n:
            break
        if text[i] != "(":
            raise ValueError(f"expected '(' at position {i}: {text[max(0,i-20):i+20]!r}")
        i += 1  # consume '('
        row: list = []
        while True:
            while i < n and text[i] == " ":
                i += 1
            if text[i] == "'":
                i += 1
                buf = []
                while True:
                    c = text[i]
                    if c == "\\":
                        nxt = text[i + 1]
                        buf.append({"n": "\n", "r": "\r", "0": "\0", "Z": "\x1a",
                                    "'": "'", '"': '"', "\\": "\\"}.get(nxt, nxt))
                        i += 2
                    elif c == "'":
                        i += 1
                        break
                    else:
                        buf.append(c)
                        i += 1
                row.append("".join(buf))
            elif text[i:i + 4] == "NULL":
                row.append(None)
                i += 4
            else:
                j = i
                while j < n and text[j] not in ",)":
                    j += 1
                token = text[i:j]
                row.append(float(token) if ("." in token or "e" in token.lower()) else int(token))
                i = j
            while i < n and text[i] == " ":
                i += 1
            if text[i] == ",":
                i += 1
                continue
            if text[i] == ")":
                i += 1
                break
            raise ValueError(f"unexpected char {text[i]!r} at {i}: {text[max(0,i-20):i+20]!r}")
        yield row
