"""Shared run-loop for specialist agents that explain graph findings.

Planning, Progress, and Workload all follow the same shape: try the LLM with
the compact witness-subgraph prompt (falling back to the legacy raw-data
prompt when no graph context was supplied — e.g. the single-agent diagnostic
endpoint called directly), enforce evidence grounding (R4), and fall back to
the deterministic rule-based method on any failure. Factoring this out once
keeps that contract identical across all three instead of drifting per-agent.
"""

from __future__ import annotations

from typing import Callable, Optional, TypeVar

from pydantic import BaseModel

from app.graph.grounding import drop_ungrounded
from app.llm.client import GroqClient

OutputT = TypeVar("OutputT", bound=BaseModel)


async def run_graph_grounded(
    llm: GroqClient,
    system_prompt: str,
    user_prompt: str,
    output_model: type[OutputT],
    finding_ids: Optional[list[str]],
    fallback: Callable[[], OutputT],
) -> OutputT:
    """Call the LLM, ground its citations, and fall back on any failure.

    ``finding_ids=None`` means the legacy (non-graph) path was used and no
    grounding applies. ``finding_ids=[]`` — a graph run with zero findings —
    still grounds: with nothing in the allowed set, any citation the LLM
    invents is stripped. Only a non-empty allowed set can validate a
    reference; the empty case must not be mistaken for "grounding off".

    A response is never returned with a fabricated evidence reference: any
    citation outside ``finding_ids`` is stripped before the payload is parsed
    into ``output_model`` (see app.graph.grounding — REL-1).
    """
    try:
        response = await llm.generate_structured(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output_schema=output_model.model_json_schema(),
        )
        if finding_ids is not None:
            response = drop_ungrounded(response, finding_ids)
        return output_model(**response)
    except Exception:
        return fallback()
