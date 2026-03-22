"""Reviewer agents: SkepticReviewer, SecurityReviewer, RegressionReviewer."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import AgentTemplate, Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import REVIEWER_SCHEMA


class _BaseReviewer(BaseAgent):
    """Shared logic for all reviewer types."""

    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=REVIEWER_SCHEMA)

        issues = result.get("issues", [])
        verdict = result.get("verdict", "unknown")
        artifact = Artifact(
            artifact_type=ArtifactType.REVIEW,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=f"{context.node.template.value}: {verdict}, {len(issues)} issue(s)",
        )
        self.artifact_store.put(artifact)
        return [artifact]


class SkepticReviewer(_BaseReviewer):
    pass


class SecurityReviewer(_BaseReviewer):
    pass


class RegressionReviewer(_BaseReviewer):
    pass


REVIEWER_MAP: dict[AgentTemplate, type[_BaseReviewer]] = {
    AgentTemplate.SKEPTIC_REVIEWER: SkepticReviewer,
    AgentTemplate.SECURITY_REVIEWER: SecurityReviewer,
    AgentTemplate.REGRESSION_REVIEWER: RegressionReviewer,
}
