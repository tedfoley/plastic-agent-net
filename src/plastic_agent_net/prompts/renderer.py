"""PromptRenderer: compose template+persona+context+schema into LLM messages."""

from __future__ import annotations

import json
from typing import Any

from plastic_agent_net.config.templates import TEMPLATE_CONFIGS
from plastic_agent_net.core.models import NodeState
from plastic_agent_net.prompts.schemas import AGENT_SCHEMAS


class PromptRenderer:
    """Composes prompts from structured components."""

    def render(
        self,
        node: NodeState,
        task_summary: str,
        branch_summary: str = "",
        artifact_summaries: list[dict] | None = None,
        tool_outputs: list[dict] | None = None,
        messages: list[dict] | None = None,
        output_schema: dict | None = None,
    ) -> tuple[str, list[dict[str, str]]]:
        """Build system prompt and user messages for an agent call.

        Returns (system_prompt, messages) tuple.
        """
        template_config = TEMPLATE_CONFIGS[node.template]

        # --- System prompt ---
        system_parts = [
            template_config.instruction,
            "",
            "## Persona",
            node.persona.render(),
            "",
            f"## Allowed Tools: {', '.join(template_config.allowed_tools)}",
        ]

        if output_schema is None:
            output_schema = AGENT_SCHEMAS.get(node.template)

        if output_schema:
            system_parts.extend([
                "",
                "## Output Format",
                "Respond with a JSON object matching this schema:",
                f"```json\n{json.dumps(output_schema, indent=2)}\n```",
            ])

        system_prompt = "\n".join(system_parts)

        # --- User messages ---
        user_parts = [f"## Task\n{task_summary}"]

        if branch_summary:
            user_parts.append(f"\n## Branch Context\n{branch_summary}")

        if artifact_summaries:
            user_parts.append("\n## Relevant Artifacts")
            for art in artifact_summaries:
                user_parts.append(
                    f"- [{art.get('type', '?')}] by {art.get('producer', '?')} "
                    f"(round {art.get('round', '?')}): {art.get('summary', 'N/A')}"
                )

        if tool_outputs:
            user_parts.append("\n## Tool Outputs")
            for to in tool_outputs:
                user_parts.append(f"### {to.get('tool', 'unknown')}")
                user_parts.append(f"```\n{to.get('output', '')}\n```")

        if messages:
            user_parts.append("\n## Messages from Other Agents")
            for msg in messages:
                user_parts.append(
                    f"- [{msg.get('type', '?')}] from {msg.get('sender', '?')}: "
                    f"{msg.get('payload', '')}"
                )

        user_content = "\n".join(user_parts)
        llm_messages = [{"role": "user", "content": user_content}]

        return system_prompt, llm_messages

    def render_task_encoder(self, user_request: str, repo_summary: str) -> tuple[str, list[dict[str, str]]]:
        """Render prompt for TaskEncoder (uses simpler format)."""
        system = (
            "You are a task classification agent. Analyze the user's request and the repo "
            "structure to determine the task type, complexity, relevant keywords, and "
            "candidate files.\n\n"
            "Respond with a JSON object matching this schema:\n"
            f"```json\n{json.dumps(AGENT_SCHEMAS.get(None, {}), indent=2)}\n```"
        )
        user_content = f"## User Request\n{user_request}\n\n## Repository\n{repo_summary}"
        return system, [{"role": "user", "content": user_content}]
