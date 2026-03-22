"""VerifierCoordinator agent: schedules verification, interprets results, computes branch scores."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import VERIFIER_SCHEMA


class VerifierCoordinatorAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=VERIFIER_SCHEMA)

        artifact = Artifact(
            artifact_type=ArtifactType.VERIFICATION,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=(
                f"build={'pass' if result.get('build_passed') else 'fail'} "
                f"tests={'pass' if result.get('tests_passed') else 'fail'} "
                f"score={result.get('overall_score', 0)}"
            ),
        )
        self.artifact_store.put(artifact)
        return [artifact]
