"""Async dispatcher: dependency-aware parallel execution of agents."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.agents.coder import CoderAgent
from plastic_agent_net.agents.planner import PlannerAgent
from plastic_agent_net.agents.repo_mapper import RepoMapperAgent
from plastic_agent_net.agents.verifier_coordinator import VerifierCoordinatorAgent
from plastic_agent_net.core.budgets import BudgetWatchdog
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.messages import MessageBus
from plastic_agent_net.core.models import (
    AgentTemplate,
    Artifact,
    NodeState,
    NodeStatus,
)
from plastic_agent_net.llm.client import AnthropicClient
from plastic_agent_net.memory.artifact_store import ArtifactStore
from plastic_agent_net.prompts.renderer import PromptRenderer

logger = logging.getLogger(__name__)


# Lazy imports for agents added in later phases
def _get_agent_class(template: AgentTemplate) -> type[BaseAgent]:
    """Get the agent class for a template, with lazy imports for optional agents."""
    _AGENT_MAP: dict[AgentTemplate, type[BaseAgent]] = {
        AgentTemplate.PLANNER: PlannerAgent,
        AgentTemplate.REPO_MAPPER: RepoMapperAgent,
        AgentTemplate.CODER: CoderAgent,
        AgentTemplate.VERIFIER_COORDINATOR: VerifierCoordinatorAgent,
    }
    cls = _AGENT_MAP.get(template)
    if cls:
        return cls

    # Lazy imports for Phase 5 agents
    if template == AgentTemplate.DEBUGGER:
        from plastic_agent_net.agents.debugger import DebuggerAgent
        return DebuggerAgent
    if template == AgentTemplate.TEST_WRITER:
        from plastic_agent_net.agents.test_writer import TestWriterAgent
        return TestWriterAgent
    if template in (AgentTemplate.SKEPTIC_REVIEWER, AgentTemplate.SECURITY_REVIEWER, AgentTemplate.REGRESSION_REVIEWER):
        from plastic_agent_net.agents.reviewer import REVIEWER_MAP
        return REVIEWER_MAP[template]
    if template == AgentTemplate.SYNTHESIZER:
        from plastic_agent_net.agents.synthesizer import SynthesizerAgent
        return SynthesizerAgent

    raise ValueError(f"Unknown agent template: {template}")


class Dispatcher:
    """Executes agents in dependency-aware parallel waves."""

    def __init__(
        self,
        graph: AgentGraph,
        llm: AnthropicClient,
        artifact_store: ArtifactStore,
        message_bus: MessageBus,
        budget: BudgetWatchdog,
        task_summary: str = "",
        repo_path: str = "",
    ) -> None:
        self._graph = graph
        self._llm = llm
        self._artifact_store = artifact_store
        self._message_bus = message_bus
        self._budget = budget
        self._task_summary = task_summary
        self._repo_path = repo_path
        self._renderer = PromptRenderer()

    async def dispatch_round(self, current_round: int) -> dict[str, list[Artifact]]:
        """Execute one round: topological waves, parallel within each wave."""
        results: dict[str, list[Artifact]] = {}
        waves = self._graph.topological_waves()

        for wave in waves:
            self._budget.check(self._graph)

            tasks = []
            for node_id in wave:
                node = self._graph.get_node(node_id)
                if node is None or node.status != NodeStatus.PENDING:
                    continue
                tasks.append(self._run_node(node, current_round))

            wave_results = await asyncio.gather(*tasks, return_exceptions=True)

            for node_id, result in zip(wave, wave_results):
                if isinstance(result, Exception):
                    logger.error("Node %s failed: %s", node_id, result)
                    results[node_id] = []
                else:
                    results[node_id] = result

        return results

    async def _run_node(self, node: NodeState, current_round: int) -> list[Artifact]:
        """Execute a single node's agent."""
        node.status = NodeStatus.RUNNING
        node.rounds_active += 1

        # Gather context
        messages_raw = self._message_bus.receive(node.node_id, current_round)
        msg_dicts = [
            {
                "type": m.message_type.value,
                "sender": m.sender,
                "payload": str(m.payload),
            }
            for m in messages_raw
        ]

        artifact_summaries = self._artifact_store.summarize_for_node(
            node.node_id, node.branch_id
        )

        branch_nodes = self._graph.nodes_by_branch(node.branch_id)
        branch_summary = f"Branch '{node.branch_id}' has {len(branch_nodes)} nodes"

        context = AgentContext(
            node=node,
            task_summary=self._task_summary,
            branch_summary=branch_summary,
            artifact_summaries=artifact_summaries,
            messages=msg_dicts,
            repo_path=self._repo_path,
            current_round=current_round,
        )

        agent_cls = _get_agent_class(node.template)
        agent = agent_cls(
            llm=self._llm,
            artifact_store=self._artifact_store,
            renderer=self._renderer,
        )

        try:
            artifacts = await agent.run(context)
            node.status = NodeStatus.DONE
            self._budget.record_tokens(node.tokens_used)
            return artifacts
        except Exception:
            node.status = NodeStatus.DONE
            raise
