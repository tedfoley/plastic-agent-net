"""RepoMapper agent: inspects repo structure, identifies relevant files/symbols."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import REPO_MAP_SCHEMA


class RepoMapperAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=REPO_MAP_SCHEMA)

        artifact = Artifact(
            artifact_type=ArtifactType.REPO_MAP,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=f"Mapped {len(result.get('relevant_files', []))} relevant files",
        )
        self.artifact_store.put(artifact)
        return [artifact]
