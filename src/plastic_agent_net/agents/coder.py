"""Coder agent: proposes concrete patches with rationale and risk notes."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import CODER_SCHEMA


class CoderAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=CODER_SCHEMA)

        patches = result.get("patches", [])
        artifact = Artifact(
            artifact_type=ArtifactType.PATCH,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=f"{len(patches)} patch(es), confidence={result.get('confidence', 'N/A')}",
        )
        self.artifact_store.put(artifact)
        return [artifact]
