"""Tests for Episode lifecycle (mock LLM)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from plastic_agent_net.core.models import BudgetConfig
from plastic_agent_net.llm.client import AnthropicClient, LLMResponse
from plastic_agent_net.runtime.episode import Episode


def _make_mock_llm():
    llm = MagicMock(spec=AnthropicClient)
    # Return planner-style response by default
    llm.call = AsyncMock(return_value=LLMResponse(
        content='{"sub_tasks": [], "strategy": "test"}',
        parsed={"sub_tasks": [], "strategy": "test", "task_type": "bugfix", "complexity": "low"},
        input_tokens=50,
        output_tokens=30,
    ))
    llm.close = AsyncMock()
    return llm


@pytest.mark.asyncio
async def test_episode_runs_and_terminates():
    llm = _make_mock_llm()
    budget = BudgetConfig(max_rounds=2, max_total_tokens=10000, max_wall_seconds=30)

    events = []
    episode = Episode(
        llm=llm,
        repo_path="",
        budget_config=budget,
        event_callback=lambda e: events.append(e),
    )

    result = await episode.run("Fix test bug")

    assert result.rounds_completed <= 2
    assert result.terminated_reason != ""
    assert len(events) > 0


@pytest.mark.asyncio
async def test_episode_produces_artifacts():
    llm = _make_mock_llm()
    budget = BudgetConfig(max_rounds=1, max_total_tokens=50000, max_wall_seconds=30)

    episode = Episode(llm=llm, budget_config=budget)
    result = await episode.run("Add logging")

    # Should have at least some artifacts from seed agents
    assert isinstance(result.final_artifacts, list)


@pytest.mark.asyncio
async def test_episode_respects_budget():
    llm = _make_mock_llm()
    budget = BudgetConfig(max_rounds=1, max_total_tokens=100, max_wall_seconds=30)

    episode = Episode(llm=llm, budget_config=budget)
    result = await episode.run("Refactor utils")

    # Should terminate due to budget
    assert result.rounds_completed <= 1
