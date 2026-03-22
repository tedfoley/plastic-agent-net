"""Synthesizer agent: merge best patch with accepted critiques into final candidate."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import SYNTHESIZER_SCHEMA


class SynthesizerAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=SYNTHESIZER_SCHEMA)

        patches = result.get("final_patches", [])
        artifact = Artifact(
            artifact_type=ArtifactType.SYNTHESIS,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=f"Synthesized {len(patches)} patch(es): {result.get('changes_summary', '')[:80]}",
        )
        self.artifact_store.put(artifact)
        return [artifact]
