"""Debugger agent: root-cause localization from failure traces."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import DEBUGGER_SCHEMA


class DebuggerAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=DEBUGGER_SCHEMA)

        artifact = Artifact(
            artifact_type=ArtifactType.DEBUG_REPORT,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=f"Root cause: {result.get('root_cause', 'unknown')[:80]} (conf={result.get('confidence', 0)})",
        )
        self.artifact_store.put(artifact)
        return [artifact]
