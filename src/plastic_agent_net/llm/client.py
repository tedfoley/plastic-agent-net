"""Async Anthropic client wrapper with tier-aware model selection."""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from plastic_agent_net.config.defaults import MODEL_MAP, TIER_MAX_TOKENS
from plastic_agent_net.core.models import ModelTier

logger = logging.getLogger(__name__)


class LLMResponse:
    """Parsed response from an LLM call."""

    def __init__(self, content: str, parsed: dict[str, Any] | None, input_tokens: int, output_tokens: int) -> None:
        self.content = content
        self.parsed = parsed
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens


class AnthropicClient:
    """Async client for Anthropic Claude models with tier selection."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = anthropic.AsyncAnthropic(api_key=api_key)

    async def call(
        self,
        messages: list[dict[str, str]],
        model_tier: ModelTier = ModelTier.HAIKU,
        system: str = "",
        json_schema: dict[str, Any] | None = None,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Make an async LLM call and return parsed response."""
        model = MODEL_MAP[model_tier]
        if max_tokens is None:
            max_tokens = TIER_MAX_TOKENS[model_tier]

        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        # Use structured outputs (constrained decoding) when a schema is provided
        if json_schema is not None:
            kwargs["output_config"] = {
                "format": {
                    "type": "json_schema",
                    "schema": json_schema,
                }
            }

        response = await self._client.messages.create(**kwargs)

        content = ""
        for block in response.content:
            if block.type == "text":
                content = block.text
                break

        parsed = None
        if json_schema is not None:
            # With structured outputs the response should be valid JSON,
            # but keep fallback parsing for robustness
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                # Fallback: strip markdown fences and extract JSON
                text = content.strip()
                if text.startswith("```"):
                    first_newline = text.find("\n")
                    if first_newline >= 0:
                        text = text[first_newline + 1:]
                    if text.endswith("```"):
                        text = text[:-3]
                    text = text.strip()
                try:
                    parsed = json.loads(text)
                except json.JSONDecodeError:
                    start = text.find("{")
                    end = text.rfind("}") + 1
                    if start >= 0 and end > start:
                        try:
                            parsed = json.loads(text[start:end])
                        except json.JSONDecodeError:
                            logger.warning("Failed to parse JSON from LLM response")

        return LLMResponse(
            content=content,
            parsed=parsed,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )

    async def close(self) -> None:
        await self._client.close()
