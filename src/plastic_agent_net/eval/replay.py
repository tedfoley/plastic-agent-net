"""Episode replay from JSONL logs."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ReplayState:
    """Reconstructed state at a point in the episode."""
    round: int = 0
    events: list[dict[str, Any]] = field(default_factory=list)
    branch_scores: dict[str, float] = field(default_factory=dict)
    nodes_run: int = 0
    total_actions: int = 0
    tokens_used: int = 0


class EpisodeReplay:
    """Load and replay JSONL logs to reconstruct episode state."""

    def __init__(self, log_path: str | Path) -> None:
        self._path = Path(log_path)
        self._events: list[dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        with open(self._path) as f:
            for line in f:
                line = line.strip()
                if line:
                    self._events.append(json.loads(line))

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    @property
    def total_rounds(self) -> int:
        return max(
            (e.get("round", 0) for e in self._events if "round" in e),
            default=0,
        ) + 1

    def state_at_round(self, target_round: int) -> ReplayState:
        """Reconstruct state up to and including the target round."""
        state = ReplayState(round=target_round)

        for event in self._events:
            event_round = event.get("round", 0)
            if event_round > target_round:
                break

            state.events.append(event)
            etype = event.get("event", "")

            if etype == "round_dispatched":
                state.nodes_run += event.get("nodes_run", 0)
            elif etype == "controller_step":
                state.total_actions += event.get("actions", 0)
                state.branch_scores = event.get("branch_scores", {})
            elif etype == "episode_complete":
                result = event.get("result", {})
                state.tokens_used = result.get("tokens_used", 0)

        return state

    def summary(self) -> dict[str, Any]:
        """Generate a summary of the full episode."""
        final = [e for e in self._events if e.get("event") == "episode_complete"]
        result = final[0].get("result", {}) if final else {}

        return {
            "total_events": len(self._events),
            "total_rounds": self.total_rounds,
            "tokens_used": result.get("tokens_used", 0),
            "terminated_reason": result.get("terminated_reason", "unknown"),
            "branch_scores": result.get("branch_scores", {}),
            "artifacts_count": len(result.get("final_artifacts", [])),
        }
