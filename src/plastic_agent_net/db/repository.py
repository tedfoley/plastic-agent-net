"""SupabaseRepository: CRUD for episodes, nodes, edges, artifacts, messages, events."""

from __future__ import annotations

from typing import Any

from supabase import Client

from plastic_agent_net.core.models import (
    Artifact,
    ArtifactType,
    BudgetConfig,
    ControllerAction,
    EdgeState,
    MessageType,
    ModelTier,
    NodeState,
    NodeStatus,
    PersonaVector,
)


class SupabaseRepository:
    """Persistent store backed by Supabase Postgres."""

    def __init__(self, client: Client) -> None:
        self._sb = client

    # ----------------------------------------------------------
    # Episodes
    # ----------------------------------------------------------

    def create_episode(
        self,
        task: str,
        repo_path: str = "",
        budget_config: BudgetConfig | None = None,
    ) -> str:
        """Create a new episode, return its UUID."""
        data: dict[str, Any] = {
            "task": task,
            "repo_path": repo_path,
            "status": "pending",
        }
        if budget_config:
            data["budget_config"] = {
                "max_total_tokens": budget_config.max_total_tokens,
                "max_round_tokens": budget_config.max_round_tokens,
                "max_rounds": budget_config.max_rounds,
                "max_nodes": budget_config.max_nodes,
                "max_edges": budget_config.max_edges,
                "max_branches": budget_config.max_branches,
                "max_wall_seconds": budget_config.max_wall_seconds,
            }
        result = self._sb.table("episodes").insert(data).execute()
        return result.data[0]["id"]

    def update_episode(self, episode_id: str, **kwargs: Any) -> None:
        """Update episode fields."""
        self._sb.table("episodes").update(kwargs).eq("id", episode_id).execute()

    def get_episode(self, episode_id: str) -> dict[str, Any] | None:
        """Fetch a single episode."""
        result = self._sb.table("episodes").select("*").eq("id", episode_id).execute()
        return result.data[0] if result.data else None

    def list_episodes(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent episodes."""
        result = (
            self._sb.table("episodes")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data

    # ----------------------------------------------------------
    # Nodes
    # ----------------------------------------------------------

    def upsert_node(self, episode_id: str, node: NodeState) -> None:
        """Insert or update a node."""
        data = {
            "id": node.node_id,
            "episode_id": episode_id,
            "template": node.template.value,
            "persona": {
                "caution": node.persona.caution,
                "verbosity": node.persona.verbosity,
                "creativity": node.persona.creativity,
                "skepticism": node.persona.skepticism,
            },
            "model_tier": node.model_tier.value,
            "branch_id": node.branch_id,
            "status": node.status.value,
            "round_created": node.round_created,
            "rounds_active": node.rounds_active,
            "tokens_used": node.tokens_used,
            "contribution_score": node.contribution_score,
            "metadata": node.metadata,
        }
        self._sb.table("nodes").upsert(data).execute()

    def get_nodes(self, episode_id: str) -> list[dict[str, Any]]:
        """Fetch all nodes for an episode."""
        result = (
            self._sb.table("nodes")
            .select("*")
            .eq("episode_id", episode_id)
            .execute()
        )
        return result.data

    def node_from_row(self, row: dict[str, Any]) -> NodeState:
        """Convert a DB row to a NodeState."""
        persona = row.get("persona", {})
        return NodeState(
            node_id=row["id"],
            template=row["template"],
            persona=PersonaVector(
                caution=persona.get("caution", 0.5),
                verbosity=persona.get("verbosity", 0.5),
                creativity=persona.get("creativity", 0.5),
                skepticism=persona.get("skepticism", 0.5),
            ),
            model_tier=ModelTier(row.get("model_tier", "haiku")),
            branch_id=row.get("branch_id", "main"),
            status=NodeStatus(row.get("status", "pending")),
            round_created=row.get("round_created", 0),
            rounds_active=row.get("rounds_active", 0),
            tokens_used=row.get("tokens_used", 0),
            contribution_score=row.get("contribution_score", 0.0),
            metadata=row.get("metadata", {}),
        )

    # ----------------------------------------------------------
    # Edges
    # ----------------------------------------------------------

    def upsert_edge(self, episode_id: str, edge: EdgeState) -> None:
        """Insert or update an edge."""
        data = {
            "episode_id": episode_id,
            "source_node": edge.source,
            "target_node": edge.target,
            "weight": edge.weight,
            "message_types": [mt.value if isinstance(mt, MessageType) else mt for mt in edge.message_types],
            "active": edge.active,
        }
        self._sb.table("edges").upsert(data, on_conflict="episode_id,source_node,target_node").execute()

    def get_edges(self, episode_id: str) -> list[dict[str, Any]]:
        """Fetch all edges for an episode."""
        result = (
            self._sb.table("edges")
            .select("*")
            .eq("episode_id", episode_id)
            .execute()
        )
        return result.data

    def delete_edge(self, episode_id: str, source: str, target: str) -> None:
        """Delete an edge."""
        (
            self._sb.table("edges")
            .delete()
            .eq("episode_id", episode_id)
            .eq("source_node", source)
            .eq("target_node", target)
            .execute()
        )

    # ----------------------------------------------------------
    # Artifacts
    # ----------------------------------------------------------

    def insert_artifact(self, episode_id: str, artifact: Artifact) -> None:
        """Insert an artifact."""
        data = {
            "id": artifact.artifact_id,
            "episode_id": episode_id,
            "artifact_type": artifact.artifact_type.value,
            "producer_node": artifact.producer_node,
            "branch_id": artifact.branch_id,
            "round_produced": artifact.round_produced,
            "content": artifact.content,
            "summary": artifact.summary,
        }
        self._sb.table("artifacts").upsert(data).execute()

    def get_artifacts(self, episode_id: str) -> list[dict[str, Any]]:
        """Fetch all artifacts for an episode."""
        result = (
            self._sb.table("artifacts")
            .select("*")
            .eq("episode_id", episode_id)
            .execute()
        )
        return result.data

    def get_artifacts_by_type(
        self, episode_id: str, artifact_type: str
    ) -> list[dict[str, Any]]:
        """Fetch artifacts of a specific type."""
        result = (
            self._sb.table("artifacts")
            .select("*")
            .eq("episode_id", episode_id)
            .eq("artifact_type", artifact_type)
            .execute()
        )
        return result.data

    def get_artifacts_by_branch(
        self, episode_id: str, branch_id: str
    ) -> list[dict[str, Any]]:
        """Fetch artifacts for a specific branch."""
        result = (
            self._sb.table("artifacts")
            .select("*")
            .eq("episode_id", episode_id)
            .eq("branch_id", branch_id)
            .execute()
        )
        return result.data

    # ----------------------------------------------------------
    # Messages
    # ----------------------------------------------------------

    def insert_message(self, episode_id: str, msg_id: str, msg_type: str,
                       sender: str, receiver: str, payload: dict,
                       round_sent: int, ttl: int = 3) -> None:
        """Insert a message."""
        data = {
            "id": msg_id,
            "episode_id": episode_id,
            "message_type": msg_type,
            "sender": sender,
            "receiver": receiver,
            "payload": payload,
            "round_sent": round_sent,
            "ttl": ttl,
        }
        self._sb.table("messages").upsert(data).execute()

    # ----------------------------------------------------------
    # Events
    # ----------------------------------------------------------

    def insert_event(self, episode_id: str, event_type: str,
                     round_num: int | None, payload: dict) -> None:
        """Insert an event log entry."""
        data: dict[str, Any] = {
            "episode_id": episode_id,
            "event_type": event_type,
            "payload": payload,
        }
        if round_num is not None:
            data["round"] = round_num
        self._sb.table("events").insert(data).execute()

    def get_events(self, episode_id: str) -> list[dict[str, Any]]:
        """Fetch all events for an episode."""
        result = (
            self._sb.table("events")
            .select("*")
            .eq("episode_id", episode_id)
            .order("created_at")
            .execute()
        )
        return result.data

    # ----------------------------------------------------------
    # Controller Actions
    # ----------------------------------------------------------

    def insert_controller_action(
        self, episode_id: str, action: ControllerAction, round_num: int
    ) -> None:
        """Record a controller action."""
        data = {
            "episode_id": episode_id,
            "action_type": action.action_type.value,
            "target_node": action.target_node,
            "payload": action.payload,
            "reason": action.reason,
            "round": round_num,
        }
        self._sb.table("controller_actions").insert(data).execute()

    # ----------------------------------------------------------
    # Bulk sync helpers
    # ----------------------------------------------------------

    def sync_graph_state(
        self, episode_id: str, nodes: list[NodeState], edges: list[EdgeState]
    ) -> None:
        """Bulk upsert all nodes and edges for an episode."""
        for node in nodes:
            self.upsert_node(episode_id, node)
        for edge in edges:
            self.upsert_edge(episode_id, edge)

    def sync_artifacts(self, episode_id: str, artifacts: list[Artifact]) -> None:
        """Bulk upsert all artifacts for an episode."""
        for artifact in artifacts:
            self.insert_artifact(episode_id, artifact)
