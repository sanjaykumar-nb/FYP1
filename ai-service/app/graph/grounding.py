"""Evidence grounding — reject citations that do not resolve to real nodes.

"Every recommendation includes evidence references" is only a real guarantee if
something checks it. An agent may cite only node ids that were present in the
witness subgraph it was shown; anything else is a fabrication and is rejected
before the output is returned.

Functions take a plain iterable of allowed ids rather than a WitnessSubgraph
object, so callers that only have the id list (e.g. an agent holding
``PlanningInput.finding_ids``) don't need graph internals to check grounding.
"""

from __future__ import annotations

from typing import Iterable


class GroundingError(ValueError):
    """Raised when an agent cites evidence that is not in its witness subgraph."""

    def __init__(self, bad_refs: list[str]):
        self.bad_refs = bad_refs
        super().__init__(
            f"Ungrounded evidence references: {', '.join(bad_refs[:5])}"
            + (" ..." if len(bad_refs) > 5 else "")
        )


def extract_references(payload: dict) -> list[str]:
    """Collect every evidence reference an agent output claims."""
    refs: list[str] = []
    for item in payload.get("evidence") or []:
        if isinstance(item, dict):
            ref = item.get("reference_id")
            if ref:
                refs.append(str(ref))
    return refs


def check_grounding(payload: dict, allowed_ids: Iterable[str]) -> list[str]:
    """Return the references that are NOT in the allowed set."""
    allowed = set(allowed_ids)
    return [r for r in extract_references(payload) if r not in allowed]


def enforce_grounding(payload: dict, allowed_ids: Iterable[str]) -> dict:
    """Raise if any citation is fabricated. Callers fall back on GroundingError."""
    bad = check_grounding(payload, allowed_ids)
    if bad:
        raise GroundingError(bad)
    return payload


def drop_ungrounded(payload: dict, allowed_ids: Iterable[str]) -> dict:
    """Non-fatal variant: strip fabricated citations, keep the rest.

    Used so a single bad reference does not cost the whole analysis, while
    still guaranteeing nothing ungrounded is ever returned.
    """
    allowed = set(allowed_ids)
    evidence = payload.get("evidence") or []
    payload = dict(payload)
    payload["evidence"] = [
        e for e in evidence
        if not isinstance(e, dict)
        or not e.get("reference_id")
        or str(e["reference_id"]) in allowed
    ]
    return payload
