"""Planner agent: decomposes tasks, flags uncertainty, proposes strategy."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import PLANNER_SCHEMA


class PlannerAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=PLANNER_SCHEMA)

        artifact = Artifact(
            artifact_type=ArtifactType.PLAN,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=result.get("strategy", "Plan produced"),
        )
        self.artifact_store.put(artifact)
        return [artifact]
