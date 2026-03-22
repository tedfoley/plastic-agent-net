"""BudgetWatchdog: enforce hard limits on token/time/node/edge/branch usage."""

from __future__ import annotations

import time

from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import BudgetConfig, BudgetUsage


class BudgetExceeded(Exception):
    """Raised when a hard budget limit is exceeded."""

    def __init__(self, resource: str, current: float, limit: float) -> None:
        self.resource = resource
        self.current = current
        self.limit = limit
        super().__init__(f"Budget exceeded: {resource} ({current}/{limit})")


class BudgetWatchdog:
    """Tracks resource usage and enforces hard caps."""

    def __init__(self, config: BudgetConfig | None = None) -> None:
        self.config = config or BudgetConfig()
        self.usage = BudgetUsage(start_time=time.time())

    def record_tokens(self, tokens: int) -> None:
        self.usage.total_tokens += tokens
        self.usage.round_tokens += tokens

    def new_round(self) -> None:
        self.usage.rounds_completed += 1
        self.usage.round_tokens = 0

    def sync_from_graph(self, graph: AgentGraph) -> None:
        self.usage.active_nodes = graph.node_count()
        self.usage.active_edges = graph.edge_count()
        self.usage.active_branches = len(graph.branch_ids())

    def check(self, graph: AgentGraph | None = None) -> None:
        """Raise BudgetExceeded if any hard limit is violated."""
        if graph:
            self.sync_from_graph(graph)

        checks = [
            ("total_tokens", self.usage.total_tokens, self.config.max_total_tokens),
            ("round_tokens", self.usage.round_tokens, self.config.max_round_tokens),
            ("rounds", self.usage.rounds_completed, self.config.max_rounds),
            ("nodes", self.usage.active_nodes, self.config.max_nodes),
            ("edges", self.usage.active_edges, self.config.max_edges),
            ("branches", self.usage.active_branches, self.config.max_branches),
        ]
        for resource, current, limit in checks:
            if current > limit:
                raise BudgetExceeded(resource, current, limit)

        elapsed = time.time() - self.usage.start_time
        if elapsed > self.config.max_wall_seconds:
            raise BudgetExceeded("wall_seconds", elapsed, self.config.max_wall_seconds)

    def remaining_tokens(self) -> int:
        return max(0, self.config.max_total_tokens - self.usage.total_tokens)

    def remaining_rounds(self) -> int:
        return max(0, self.config.max_rounds - self.usage.rounds_completed)

    def pressure(self) -> float:
        """Return 0-1 value indicating how close we are to budget limits."""
        ratios = [
            self.usage.total_tokens / max(1, self.config.max_total_tokens),
            self.usage.rounds_completed / max(1, self.config.max_rounds),
            (time.time() - self.usage.start_time) / max(1, self.config.max_wall_seconds),
        ]
        return max(ratios)
