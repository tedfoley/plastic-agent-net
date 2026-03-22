"""In-memory artifact store with typed CRUD and query capabilities."""

from __future__ import annotations

from plastic_agent_net.core.models import Artifact, ArtifactType


class ArtifactStore:
    """Stores and retrieves artifacts produced by agents."""

    def __init__(self) -> None:
        self._artifacts: dict[str, Artifact] = {}

    def put(self, artifact: Artifact) -> str:
        self._artifacts[artifact.artifact_id] = artifact
        return artifact.artifact_id

    def get(self, artifact_id: str) -> Artifact | None:
        return self._artifacts.get(artifact_id)

    def list_by_branch(self, branch_id: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.branch_id == branch_id]

    def list_by_type(self, artifact_type: ArtifactType) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.artifact_type == artifact_type]

    def list_by_producer(self, node_id: str) -> list[Artifact]:
        return [a for a in self._artifacts.values() if a.producer_node == node_id]

    def list_all(self) -> list[Artifact]:
        return list(self._artifacts.values())

    def summarize_for_node(self, node_id: str, branch_id: str, max_items: int = 10) -> list[dict]:
        """Return lightweight summaries of artifacts visible to a node."""
        relevant = [
            a for a in self._artifacts.values()
            if a.branch_id == branch_id or a.branch_id == "main"
        ]
        relevant.sort(key=lambda a: a.timestamp, reverse=True)
        return [
            {
                "id": a.artifact_id,
                "type": a.artifact_type.value,
                "producer": a.producer_node,
                "summary": a.summary,
                "round": a.round_produced,
            }
            for a in relevant[:max_items]
        ]
