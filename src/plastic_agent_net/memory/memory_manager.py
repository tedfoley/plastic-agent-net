"""MemoryManager: global/branch/node scoped memory with visibility rules."""

from __future__ import annotations

from typing import Any


class MemoryManager:
    """Three-scope memory system: global episodic, branch-local, node-local."""

    def __init__(self) -> None:
        self._global: list[dict[str, Any]] = []
        self._branch: dict[str, list[dict[str, Any]]] = {}
        self._node: dict[str, list[dict[str, Any]]] = {}

    def add_global(self, entry: dict[str, Any]) -> None:
        """Add an entry visible to all nodes."""
        self._global.append(entry)

    def add_branch(self, branch_id: str, entry: dict[str, Any]) -> None:
        """Add an entry visible only to nodes on this branch."""
        self._branch.setdefault(branch_id, []).append(entry)

    def add_node(self, node_id: str, entry: dict[str, Any]) -> None:
        """Add an entry visible only to this specific node."""
        self._node.setdefault(node_id, []).append(entry)

    def get_visible(self, node_id: str, branch_id: str, max_entries: int = 20) -> list[dict[str, Any]]:
        """Get all memory entries visible to a node, most recent first."""
        entries = []
        entries.extend(self._node.get(node_id, []))
        entries.extend(self._branch.get(branch_id, []))
        entries.extend(self._global)
        # Deduplicate by content while preserving order
        seen: set[str] = set()
        unique = []
        for e in entries:
            key = str(e)
            if key not in seen:
                seen.add(key)
                unique.append(e)
        return unique[:max_entries]

    def get_global(self) -> list[dict[str, Any]]:
        return list(self._global)

    def get_branch(self, branch_id: str) -> list[dict[str, Any]]:
        return list(self._branch.get(branch_id, []))

    def clear_node(self, node_id: str) -> None:
        self._node.pop(node_id, None)

    def clear_branch(self, branch_id: str) -> None:
        self._branch.pop(branch_id, None)
