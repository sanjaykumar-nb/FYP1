"""Witness-subgraph selection and compact serialization.

This is what makes prompt cost O(anomalies) rather than O(project size). The
LLM is never shown the dataset — only the findings that were computed and the
minimal neighbourhood of graph nodes that witnesses them.

Serialization is columnar rather than JSON/repr: field names are stated once
per block instead of once per row, which is where most of the saving comes from
after subgraph selection.
"""

from __future__ import annotations

from typing import Iterable, Optional

import networkx as nx

from app.graph.builder import COMPONENT, MILESTONE, PERSON, TASK, ProjectGraph
from app.graph.metrics import Finding

DEFAULT_HOPS = 1
# Hard ceiling so a pathological graph can never blow the context window.
MAX_WITNESS_NODES = 60
# A finding like "person X is overloaded" only needs a few representative
# neighbours (a sample of their tasks), not all of them — an overloaded
# person with 300 open tasks doesn't need 300 rows to explain the finding.
# This is what keeps prompt cost O(anomalies) rather than O(that person's
# degree), which otherwise still scales with project size — see TOK-2.
MAX_NEIGHBORS_PER_SEED = 8


class WitnessSubgraph:
    """The nodes an agent is allowed to see — and to cite."""

    def __init__(self, graph: ProjectGraph, node_ids: list[str], findings: list[Finding]):
        self.graph = graph
        self.node_ids = node_ids
        self.findings = findings

    def allowed_ids(self) -> set[str]:
        return set(self.node_ids)

    def render(self) -> str:
        """Compact columnar text for the user prompt."""
        g = self.graph
        lines: list[str] = []

        if self.findings:
            lines.append("findings(risk,severity,metric,value,title):")
            for f in self.findings:
                lines.append(
                    f"{f.risk_type},{f.severity},{f.metric},{f.value:g},{_clean(f.title)}"
                )

        people = [n for n in self.node_ids if g.attrs(n).get("kind") == PERSON]
        if people:
            lines.append("people(id,name,open_points):")
            load = _open_points_by_person(g)
            for n in people:
                a = g.attrs(n)
                lines.append(f"{n},{_clean(a.get('name', ''))},{load.get(n, 0)}")

        tasks = [n for n in self.node_ids if g.attrs(n).get("kind") == TASK]
        if tasks:
            lines.append("tasks(id,status,pts,due,title):")
            for n in tasks:
                a = g.attrs(n)
                due = a.get("due_date")
                due_s = due.date().isoformat() if due else "-"
                lines.append(
                    f"{n},{a.get('status', '?')},{a.get('points', 0)},{due_s},"
                    f"{_clean(a.get('title', ''))}"
                )

        comps = [n for n in self.node_ids
                 if g.attrs(n).get("kind") in (COMPONENT, MILESTONE)]
        if comps:
            lines.append("components(id,name):")
            for n in comps:
                lines.append(f"{n},{_clean(g.attrs(n).get('name', ''))}")

        edges = self._induced_edges()
        if edges:
            lines.append("edges(kind,from,to):")
            for kind, u, v in edges:
                lines.append(f"{kind},{u},{v}")

        return "\n".join(lines)

    def _induced_edges(self) -> list[tuple[str, str, str]]:
        allowed = self.allowed_ids()
        out = set()
        for u, v, data in self.graph.G.edges(data=True):
            if u in allowed and v in allowed:
                out.add((data.get("kind", "?"), u, v))
        return sorted(out)


class SubgraphSelector:
    """Extracts the k-hop neighbourhood around the nodes a finding cites."""

    def __init__(
        self,
        hops: int = DEFAULT_HOPS,
        max_nodes: int = MAX_WITNESS_NODES,
        max_neighbors_per_seed: int = MAX_NEIGHBORS_PER_SEED,
    ):
        self.hops = hops
        self.max_nodes = max_nodes
        self.max_neighbors_per_seed = max_neighbors_per_seed

    def select(self, graph: ProjectGraph, findings: list[Finding]) -> WitnessSubgraph:
        seeds: list[str] = []
        for f in findings:
            for nid in f.node_ids:
                if graph.has_node(nid) and nid not in seeds:
                    seeds.append(nid)

        undirected = graph.G.to_undirected(as_view=True)
        selected: list[str] = list(seeds)
        frontier = list(seeds)

        for _ in range(self.hops):
            nxt: list[str] = []
            for node in frontier:
                # Sampled, not exhaustive: a high-degree node (e.g. an
                # overloaded person with hundreds of tasks) contributes only
                # a representative slice of its neighbours per seed.
                neighbors = sorted(undirected.neighbors(node))[: self.max_neighbors_per_seed]
                for nbr in neighbors:
                    if nbr not in selected:
                        selected.append(nbr)
                        nxt.append(nbr)
                    if len(selected) >= self.max_nodes:
                        break
                if len(selected) >= self.max_nodes:
                    break
            frontier = nxt
            if len(selected) >= self.max_nodes:
                break

        # Seeds always survive truncation — they are what the findings cite.
        if len(selected) > self.max_nodes:
            keep = list(seeds[: self.max_nodes])
            for n in selected:
                if len(keep) >= self.max_nodes:
                    break
                if n not in keep:
                    keep.append(n)
            selected = keep

        return WitnessSubgraph(graph, selected, findings)


def _open_points_by_person(graph: ProjectGraph) -> dict[str, int]:
    attrs = graph.task_attrs()
    load: dict[str, int] = {}
    for person, task, points in graph.assignment_pairs():
        if not attrs.get(task, {}).get("is_done"):
            load[person] = load.get(person, 0) + max(points, 1)
    return load


def _clean(text: object) -> str:
    """Commas and newlines would break the columnar format."""
    s = str(text or "")
    return s.replace(",", ";").replace("\n", " ").strip()
