"""BaseAgent ABC for all agent types."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from plastic_agent_net.core.models import Artifact, NodeState, ModelTier
from plastic_agent_net.llm.client import AnthropicClient
from plastic_agent_net.memory.artifact_store import ArtifactStore
from plastic_agent_net.prompts.renderer import PromptRenderer

logger = logging.getLogger(__name__)


@dataclass
class AgentContext:
    """Everything an agent needs to execute."""
    node: NodeState
    task_summary: str
    branch_summary: str = ""
    artifact_summaries: list[dict] = field(default_factory=list)
    tool_outputs: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)
    repo_path: str = ""
    workspace_path: str = ""
    current_round: int = 0
    extra: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Abstract base for all PlasticAgentNet agents."""

    def __init__(
        self,
        llm: AnthropicClient,
        artifact_store: ArtifactStore,
        renderer: PromptRenderer | None = None,
    ) -> None:
        self.llm = llm
        self.artifact_store = artifact_store
        self.renderer = renderer or PromptRenderer()

    @abstractmethod
    async def run(self, context: AgentContext) -> list[Artifact]:
        """Execute the agent's task and return produced artifacts."""
        ...

    async def _call_llm(
        self,
        context: AgentContext,
        output_schema: dict | None = None,
        model_tier: ModelTier | None = None,
    ) -> dict[str, Any]:
        """Helper: render prompt, call LLM, return parsed JSON."""
        system, messages = self.renderer.render(
            node=context.node,
            task_summary=context.task_summary,
            branch_summary=context.branch_summary,
            artifact_summaries=context.artifact_summaries,
            tool_outputs=context.tool_outputs,
            messages=context.messages,
            output_schema=output_schema,
        )

        tier = model_tier or context.node.model_tier
        response = await self.llm.call(
            messages=messages,
            model_tier=tier,
            system=system,
            json_schema=output_schema,
        )

        context.node.tokens_used += response.total_tokens

        if response.parsed:
            return response.parsed

        logger.warning("LLM returned unparseable response for node %s", context.node.node_id)
        return {"raw_content": response.content}
