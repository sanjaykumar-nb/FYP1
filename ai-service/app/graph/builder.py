"""Compile a ProjectSnapshot into a typed knowledge graph.

Node ids are namespaced strings (``task:<uuid>``, ``person:<uuid>``, …) so that
any evidence reference an agent emits can be checked against the graph — see
``ProjectGraph.has_node`` and the grounding check in ``app.graph.grounding``.
"""

from __future__ import annotations

from typing import Iterable, Optional
from uuid import UUID

import networkx as nx

from app.graph.snapshot import ProjectSnapshot

TASK = "task"
PERSON = "person"
MILESTONE = "milestone"
COMPONENT = "component"
PROJECT = "project"

# Edge kinds
ASSIGNED_TO = "ASSIGNED_TO"
REPORTED = "REPORTED"
BLOCKS = "BLOCKS"
SUBTASK_OF = "SUBTASK_OF"
PART_OF = "PART_OF"
COMMENTED_ON = "COMMENTED_ON"
TOUCHES = "TOUCHES"
KNOWS = "KNOWS"

DONE_STATUSES = frozenset({"done"})
ACTIVE_STATUSES = frozenset({"backlog", "planned", "in_progress", "blocked", "review"})


def node_id(kind: str, raw_id: UUID | str) -> str:
    return f"{kind}:{raw_id}"


class ProjectGraph:
    """A knowledge graph over one project's state.

    Wraps a ``networkx.MultiDiGraph``. All traversal helpers return results in
    sorted order so that downstream metrics are reproducible for identical
    input — a requirement for the evaluation story.
    """

    def __init__(self, graph: nx.MultiDiGraph, snapshot: ProjectSnapshot):
        self.G = graph
        self.snapshot = snapshot

    # -- membership -------------------------------------------------------

    def has_node(self, nid: str) -> bool:
        return self.G.has_node(nid)

    def node_ids(self) -> set[str]:
        return set(self.G.nodes)

    def nodes_of(self, kind: str) -> list[str]:
        return sorted(n for n, d in self.G.nodes(data=True) if d.get("kind") == kind)

    def attrs(self, nid: str) -> dict:
        return dict(self.G.nodes[nid]) if self.G.has_node(nid) else {}

    # -- projections ------------------------------------------------------

    def edges_of_kind(self, kind: str) -> list[tuple[str, str]]:
        return sorted(
            (u, v) for u, v, d in self.G.edges(data=True) if d.get("kind") == kind
        )

    def blocks_digraph(self) -> nx.DiGraph:
        """Task-only DiGraph of BLOCKS edges (blocking -> blocked)."""
        d = nx.DiGraph()
        d.add_nodes_from(self.nodes_of(TASK))
        d.add_edges_from(self.edges_of_kind(BLOCKS))
        return d

    def assignment_pairs(self) -> list[tuple[str, str, int]]:
        """(person_id, task_id, story_points) for every assignment."""
        out = []
        for u, v, data in self.G.edges(data=True):
            if data.get("kind") == ASSIGNED_TO:
                out.append((u, v, int(data.get("points") or 0)))
        return sorted(out)

    def person_component_graph(self) -> nx.Graph:
        """Undirected bipartite person <-> component graph, for SPOF analysis."""
        g = nx.Graph()
        g.add_nodes_from(self.nodes_of(PERSON), bipartite=0)
        g.add_nodes_from(self.nodes_of(COMPONENT), bipartite=1)
        for u, v in self.edges_of_kind(KNOWS):
            g.add_edge(u, v)
        return g

    def collaboration_graph(self) -> nx.Graph:
        """People connected when they share a component or a dependency edge."""
        g = nx.Graph()
        g.add_nodes_from(self.nodes_of(PERSON))

        # Shared component
        comp_owners: dict[str, set[str]] = {}
        for person, comp in self.edges_of_kind(KNOWS):
            comp_owners.setdefault(comp, set()).add(person)
        for owners in comp_owners.values():
            ordered = sorted(owners)
            for i, a in enumerate(ordered):
                for b in ordered[i + 1 :]:
                    g.add_edge(a, b)

        # Cross-person task dependencies
        assignee_of = {t: p for p, t, _ in self.assignment_pairs()}
        for blocking, blocked in self.edges_of_kind(BLOCKS):
            pa, pb = assignee_of.get(blocking), assignee_of.get(blocked)
            if pa and pb and pa != pb:
                g.add_edge(pa, pb)
        return g

    # -- convenience ------------------------------------------------------

    def task_attrs(self) -> dict[str, dict]:
        return {n: dict(self.G.nodes[n]) for n in self.nodes_of(TASK)}

    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        for _, d in self.G.nodes(data=True):
            kinds[d.get("kind", "?")] = kinds.get(d.get("kind", "?"), 0) + 1
        edge_kinds: dict[str, int] = {}
        for _, _, d in self.G.edges(data=True):
            edge_kinds[d.get("kind", "?")] = edge_kinds.get(d.get("kind", "?"), 0) + 1
        return {
            "nodes": self.G.number_of_nodes(),
            "edges": self.G.number_of_edges(),
            "node_kinds": dict(sorted(kinds.items())),
            "edge_kinds": dict(sorted(edge_kinds.items())),
        }


class GraphBuilder:
    """Builds a ProjectGraph from a snapshot.

    Kept as a class with a single public method so an alternative persistent
    backend (Neo4j) can be dropped in behind the same interface.
    """

    def build(self, snapshot: ProjectSnapshot) -> ProjectGraph:
        g = nx.MultiDiGraph()

        project_node = node_id(PROJECT, snapshot.project_id)
        g.add_node(project_node, kind=PROJECT, name=snapshot.name)

        for m in sorted(snapshot.members, key=lambda x: str(x.id)):
            g.add_node(
                node_id(PERSON, m.id),
                kind=PERSON,
                name=m.full_name or m.email or str(m.id),
                role=m.role,
            )

        # A milestone stands in as the "component" a task touches. When richer
        # component data exists (labels, code areas), this is where it plugs in.
        for ms in sorted(snapshot.milestones, key=lambda x: str(x.id)):
            g.add_node(
                node_id(MILESTONE, ms.id),
                kind=MILESTONE,
                name=ms.name,
                target_date=ms.target_date,
                status=ms.status,
            )
            g.add_node(node_id(COMPONENT, ms.id), kind=COMPONENT, name=ms.name)

        for t in sorted(snapshot.tasks, key=lambda x: str(x.id)):
            tid = node_id(TASK, t.id)
            g.add_node(
                tid,
                kind=TASK,
                title=t.title,
                status=t.status,
                priority=t.priority,
                points=t.story_points or 0,
                due_date=t.due_date,
                completed_at=t.completed_at,
                is_done=t.status in DONE_STATUSES,
            )

            if t.assignee_id is not None:
                pid = node_id(PERSON, t.assignee_id)
                if g.has_node(pid):
                    g.add_edge(pid, tid, key=ASSIGNED_TO, kind=ASSIGNED_TO,
                               points=t.story_points or 0)
            if t.reporter_id is not None:
                rid = node_id(PERSON, t.reporter_id)
                if g.has_node(rid):
                    g.add_edge(rid, tid, key=REPORTED, kind=REPORTED)
            if t.milestone_id is not None:
                mid = node_id(MILESTONE, t.milestone_id)
                cid = node_id(COMPONENT, t.milestone_id)
                if g.has_node(mid):
                    g.add_edge(tid, mid, key=PART_OF, kind=PART_OF)
                if g.has_node(cid):
                    g.add_edge(tid, cid, key=TOUCHES, kind=TOUCHES)
            if t.parent_task_id is not None:
                parent = node_id(TASK, t.parent_task_id)
                if g.has_node(parent):
                    g.add_edge(tid, parent, key=SUBTASK_OF, kind=SUBTASK_OF)

        for dep in sorted(
            snapshot.dependencies, key=lambda d: (str(d.blocking_task_id), str(d.blocked_task_id))
        ):
            a = node_id(TASK, dep.blocking_task_id)
            b = node_id(TASK, dep.blocked_task_id)
            if g.has_node(a) and g.has_node(b):
                g.add_edge(a, b, key=BLOCKS, kind=BLOCKS, dependency_type=dep.dependency_type)

        for c in sorted(snapshot.comments, key=lambda x: (str(x.user_id), str(x.task_id))):
            p = node_id(PERSON, c.user_id)
            t = node_id(TASK, c.task_id)
            if g.has_node(p) and g.has_node(t):
                if g.has_edge(p, t, key=COMMENTED_ON):
                    g[p][t][COMMENTED_ON]["count"] += 1
                else:
                    g.add_edge(p, t, key=COMMENTED_ON, kind=COMMENTED_ON, count=1)

        graph = ProjectGraph(g, snapshot)
        self._derive_knows_edges(graph)
        return graph

    @staticmethod
    def _derive_knows_edges(graph: ProjectGraph) -> None:
        """person -[KNOWS {depth}]-> component, from ASSIGNED_TO o TOUCHES.

        ``depth`` is the number of tasks that person has worked in the
        component, which is what makes a sole owner detectable as a SPOF.
        """
        g = graph.G
        touches: dict[str, list[str]] = {}
        for task, comp in graph.edges_of_kind(TOUCHES):
            touches.setdefault(task, []).append(comp)

        depth: dict[tuple[str, str], int] = {}
        for person, task, _pts in graph.assignment_pairs():
            for comp in touches.get(task, []):
                depth[(person, comp)] = depth.get((person, comp), 0) + 1

        for (person, comp), d in sorted(depth.items()):
            g.add_edge(person, comp, key=KNOWS, kind=KNOWS, depth=d)
