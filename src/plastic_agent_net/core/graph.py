"""AgentGraph: node/edge CRUD over a networkx DiGraph."""

from __future__ import annotations

import networkx as nx

from plastic_agent_net.core.models import (
    EdgeState,
    GraphState,
    NodeState,
    NodeStatus,
)


class AgentGraph:
    """Manages the agent topology as a directed graph."""

    def __init__(self) -> None:
        self._g = nx.DiGraph()
        self._nodes: dict[str, NodeState] = {}
        self._edges: list[EdgeState] = []

    def add_node(self, node: NodeState) -> None:
        self._nodes[node.node_id] = node
        self._g.add_node(node.node_id)

    def remove_node(self, node_id: str) -> None:
        if node_id in self._nodes:
            self._nodes[node_id].status = NodeStatus.PRUNED
            self._edges = [
                e for e in self._edges
                if e.source != node_id and e.target != node_id
            ]
            self._g.remove_node(node_id)

    def get_node(self, node_id: str) -> NodeState | None:
        return self._nodes.get(node_id)

    def add_edge(self, edge: EdgeState) -> None:
        self._edges.append(edge)
        self._g.add_edge(edge.source, edge.target, weight=edge.weight)

    def remove_edge(self, source: str, target: str) -> None:
        self._edges = [
            e for e in self._edges
            if not (e.source == source and e.target == target)
        ]
        if self._g.has_edge(source, target):
            self._g.remove_edge(source, target)

    def get_edge(self, source: str, target: str) -> EdgeState | None:
        for e in self._edges:
            if e.source == source and e.target == target:
                return e
        return None

    def predecessors(self, node_id: str) -> list[str]:
        return list(self._g.predecessors(node_id))

    def successors(self, node_id: str) -> list[str]:
        return list(self._g.successors(node_id))

    def active_nodes(self) -> list[NodeState]:
        return [
            n for n in self._nodes.values()
            if n.status in (NodeStatus.PENDING, NodeStatus.RUNNING)
        ]

    def nodes_by_branch(self, branch_id: str) -> list[NodeState]:
        return [n for n in self._nodes.values() if n.branch_id == branch_id]

    def all_nodes(self) -> list[NodeState]:
        return list(self._nodes.values())

    def active_edges(self) -> list[EdgeState]:
        return [e for e in self._edges if e.active]

    def all_edges(self) -> list[EdgeState]:
        return list(self._edges)

    def topological_waves(self) -> list[list[str]]:
        """Return nodes grouped into dependency waves for parallel dispatch."""
        if not self._g.nodes:
            return []
        active_ids = {n.node_id for n in self.active_nodes()}
        sub = self._g.subgraph(active_ids & set(self._g.nodes))
        if not nx.is_directed_acyclic_graph(sub):
            return [list(active_ids)]
        waves: list[list[str]] = []
        remaining = set(sub.nodes)
        while remaining:
            wave = [
                n for n in remaining
                if not (set(sub.predecessors(n)) & remaining)
            ]
            if not wave:
                break
            waves.append(wave)
            remaining -= set(wave)
        return waves

    def branch_ids(self) -> set[str]:
        return {n.branch_id for n in self._nodes.values() if n.status not in (NodeStatus.PRUNED, NodeStatus.MERGED)}

    def node_count(self) -> int:
        return len(self.active_nodes())

    def edge_count(self) -> int:
        return len(self.active_edges())

    def snapshot(self) -> GraphState:
        return GraphState(
            nodes=dict(self._nodes),
            edges=list(self._edges),
        )
