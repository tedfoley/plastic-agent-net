"""TaskEncoder: user request → TaskProfile using fast LLM classification."""

from __future__ import annotations

import logging

from plastic_agent_net.core.models import ModelTier, TaskProfile
from plastic_agent_net.llm.client import AnthropicClient
from plastic_agent_net.prompts.schemas import TASK_ENCODER_SCHEMA
from plastic_agent_net.tools.repo import repo_summary

logger = logging.getLogger(__name__)


class TaskEncoder:
    """Encodes a user request + repo context into a structured TaskProfile."""

    def __init__(self, llm: AnthropicClient) -> None:
        self._llm = llm

    async def encode(self, user_request: str, repo_path: str) -> TaskProfile:
        """Classify and structure a user request."""
        summary = await repo_summary(repo_path)

        system = (
            "You are a task classification agent. Analyze the user's coding request "
            "and the repository structure. Determine the task type, estimated complexity, "
            "relevant keywords, and candidate files that are likely involved.\n\n"
            "Respond with a JSON object."
        )
        messages = [
            {
                "role": "user",
                "content": (
                    f"## User Request\n{user_request}\n\n"
                    f"## Repository Structure\n```\n{summary}\n```"
                ),
            }
        ]

        response = await self._llm.call(
            messages=messages,
            model_tier=ModelTier.HAIKU,
            system=system,
            json_schema=TASK_ENCODER_SCHEMA,
        )

        parsed = response.parsed or {}

        return TaskProfile(
            raw_request=user_request,
            repo_path=repo_path,
            task_type=parsed.get("task_type", "bugfix"),
            estimated_complexity=parsed.get("complexity", "medium"),
            candidate_files=parsed.get("candidate_files", []),
            keywords=parsed.get("keywords", []),
            metadata={"encoder_tokens": response.total_tokens},
        )
