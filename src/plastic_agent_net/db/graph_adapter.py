"""SupabaseGraph: AgentGraph-compatible interface backed by Postgres.

Provides the same API as AgentGraph but reads/writes through Supabase.
Includes topological_waves() via Kahn's algorithm (no networkx dependency).
"""

from __future__ import annotations

from collections import defaultdict, deque

from plastic_agent_net.core.models import (
    EdgeState,
    GraphState,
    MessageType,
    ModelTier,
    NodeState,
    NodeStatus,
    PersonaVector,
)
from plastic_agent_net.db.repository import SupabaseRepository


class SupabaseGraph:
    """Graph interface that persists to Supabase Postgres."""

    def __init__(self, repo: SupabaseRepository, episode_id: str) -> None:
        self._repo = repo
        self._episode_id = episode_id
        # Local cache, synced from DB
        self._nodes: dict[str, NodeState] = {}
        self._edges: list[EdgeState] = []

    def load(self) -> None:
        """Load current graph state from Supabase."""
        rows = self._repo.get_nodes(self._episode_id)
        self._nodes = {}
        for row in rows:
            node = self._repo.node_from_row(row)
            self._nodes[node.node_id] = node

        edge_rows = self._repo.get_edges(self._episode_id)
        self._edges = []
        for row in edge_rows:
            msg_types = row.get("message_types", [])
            edge = EdgeState(
                source=row["source_node"],
                target=row["target_node"],
                weight=row.get("weight", 1.0),
                message_types=[
                    MessageType(mt) if isinstance(mt, str) else mt for mt in msg_types
                ] if msg_types else list(MessageType),
                active=row.get("active", True),
            )
            self._edges.append(edge)

    def save(self) -> None:
        """Persist current local state to Supabase."""
        self._repo.sync_graph_state(
            self._episode_id,
            list(self._nodes.values()),
            self._edges,
        )

    # ----------------------------------------------------------
    # Node operations (mirror AgentGraph API)
    # ----------------------------------------------------------

    def add_node(self, node: NodeState) -> None:
        self._nodes[node.node_id] = node
        self._repo.upsert_node(self._episode_id, node)

    def remove_node(self, node_id: str) -> None:
        if node_id in self._nodes:
            self._nodes[node_id].status = NodeStatus.PRUNED
            self._repo.upsert_node(self._episode_id, self._nodes[node_id])
            self._edges = [
                e for e in self._edges
                if e.source != node_id and e.target != node_id
            ]
            # Delete edges from DB
            for e in list(self._edges):
                if e.source == node_id or e.target == node_id:
                    self._repo.delete_edge(self._episode_id, e.source, e.target)

    def get_node(self, node_id: str) -> NodeState | None:
        return self._nodes.get(node_id)

    def add_edge(self, edge: EdgeState) -> None:
        self._edges.append(edge)
        self._repo.upsert_edge(self._episode_id, edge)

    def remove_edge(self, source: str, target: str) -> None:
        self._edges = [
            e for e in self._edges
            if not (e.source == source and e.target == target)
        ]
        self._repo.delete_edge(self._episode_id, source, target)

    def get_edge(self, source: str, target: str) -> EdgeState | None:
        for e in self._edges:
            if e.source == source and e.target == target:
                return e
        return None

    def predecessors(self, node_id: str) -> list[str]:
        return [e.source for e in self._edges if e.target == node_id and e.active]

    def successors(self, node_id: str) -> list[str]:
        return [e.target for e in self._edges if e.source == node_id and e.active]

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
        """Compute dependency waves via Kahn's algorithm (no networkx)."""
        active_ids = {n.node_id for n in self.active_nodes()}
        if not active_ids:
            return []

        # Build adjacency and in-degree for active subgraph
        in_degree: dict[str, int] = {nid: 0 for nid in active_ids}
        adj: dict[str, list[str]] = defaultdict(list)

        for edge in self._edges:
            if edge.active and edge.source in active_ids and edge.target in active_ids:
                adj[edge.source].append(edge.target)
                in_degree[edge.target] = in_degree.get(edge.target, 0) + 1

        waves: list[list[str]] = []
        remaining = set(active_ids)

        while remaining:
            # Nodes with zero in-degree among remaining
            wave = [nid for nid in remaining if in_degree.get(nid, 0) == 0]
            if not wave:
                # Cycle detected — dump all remaining as single wave
                waves.append(list(remaining))
                break
            waves.append(wave)
            for nid in wave:
                remaining.discard(nid)
                for successor in adj.get(nid, []):
                    if successor in remaining:
                        in_degree[successor] -= 1

        return waves

    def branch_ids(self) -> set[str]:
        return {
            n.branch_id for n in self._nodes.values()
            if n.status not in (NodeStatus.PRUNED, NodeStatus.MERGED)
        }

    def node_count(self) -> int:
        return len(self.active_nodes())

    def edge_count(self) -> int:
        return len(self.active_edges())

    def snapshot(self) -> GraphState:
        return GraphState(
            nodes=dict(self._nodes),
            edges=list(self._edges),
        )
