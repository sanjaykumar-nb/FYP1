"""A fixed, project-level train/held-out split of the TAWOS sprint set.

Splitting by PROJECT, not by sprint, matters: sprints within one project
share a team's Jira conventions (how aggressively they close sprints, how
consistently they set story points, ...), so a random sprint-level split
would leak that project's own patterns into both halves and overstate how
well anything tunes. A project in the tuning set never appears in the
held-out set.

The split is written to disk once and reused everywhere else — nothing
downstream is allowed to re-randomize it, which is what makes "tune only on
the tuning half, report only on the held-out half" an enforceable rule
rather than a promise.

Run: python -m eval.datasets.tawos_split
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from eval.datasets.tawos_ingest import build_sprint_cases, connect

SPLIT_PATH = Path(__file__).parent / "tawos_split.json"
TUNING_FRACTION = 0.70


def compute_split() -> dict:
    conn = connect()
    cases = list(build_sprint_cases(conn))

    per_project: dict[str, list[bool]] = {}
    for c in cases:
        per_project.setdefault(c.project_key, []).append(c.label_delayed)

    total_sprints = len(cases)
    target_tuning = total_sprints * TUNING_FRACTION

    # Greedy bin-packing by sprint count, largest project first, always
    # assigning to whichever bucket is currently further below its target —
    # deterministic (no randomness) and doesn't depend on iteration order
    # beyond the fixed size-descending sort.
    ordered = sorted(per_project.items(), key=lambda kv: -len(kv[1]))
    tuning: list[str] = []
    holdout: list[str] = []
    tuning_n = 0
    for project_key, labels in ordered:
        if tuning_n < target_tuning:
            tuning.append(project_key)
            tuning_n += len(labels)
        else:
            holdout.append(project_key)

    def stats(keys: list[str]) -> dict:
        n = sum(len(per_project[k]) for k in keys)
        pos = sum(sum(per_project[k]) for k in keys)
        return {"n_projects": len(keys), "n_sprints": n, "positive_rate": round(pos / n, 4) if n else None}

    split = {
        "tuning_projects": sorted(tuning),
        "holdout_projects": sorted(holdout),
        "tuning_stats": stats(tuning),
        "holdout_stats": stats(holdout),
        "overall_positive_rate": round(sum(sum(v) for v in per_project.values()) / total_sprints, 4),
    }
    return split


def load_split() -> dict:
    if not SPLIT_PATH.exists():
        raise FileNotFoundError(f"{SPLIT_PATH} not found — run `python -m eval.datasets.tawos_split` first")
    return json.loads(SPLIT_PATH.read_text())


def main():
    split = compute_split()
    SPLIT_PATH.write_text(json.dumps(split, indent=2))
    print(json.dumps(split, indent=2))


if __name__ == "__main__":
    main()
