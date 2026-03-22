"""TestWriter agent: generate tests for intended behavior and regressions."""

from __future__ import annotations

from plastic_agent_net.agents.base import AgentContext, BaseAgent
from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.prompts.schemas import TEST_WRITER_SCHEMA


class TestWriterAgent(BaseAgent):
    async def run(self, context: AgentContext) -> list[Artifact]:
        result = await self._call_llm(context, output_schema=TEST_WRITER_SCHEMA)

        test_files = result.get("test_files", [])
        artifact = Artifact(
            artifact_type=ArtifactType.TEST_CODE,
            producer_node=context.node.node_id,
            branch_id=context.node.branch_id,
            round_produced=context.current_round,
            content=result,
            summary=f"Generated {len(test_files)} test file(s)",
        )
        self.artifact_store.put(artifact)
        return [artifact]
