"""Tests for Dispatcher (mock LLM)."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from plastic_agent_net.core.budgets import BudgetWatchdog
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.messages import MessageBus
from plastic_agent_net.core.models import (
    AgentTemplate,
    BudgetConfig,
    EdgeState,
    NodeState,
    NodeStatus,
)
from plastic_agent_net.llm.client import AnthropicClient, LLMResponse
from plastic_agent_net.memory.artifact_store import ArtifactStore
from plastic_agent_net.runtime.dispatcher import Dispatcher


def _make_mock_llm():
    llm = MagicMock(spec=AnthropicClient)
    llm.call = AsyncMock(return_value=LLMResponse(
        content='{"sub_tasks": [], "strategy": "test plan"}',
        parsed={"sub_tasks": [], "strategy": "test plan"},
        input_tokens=100,
        output_tokens=50,
    ))
    return llm


@pytest.mark.asyncio
async def test_dispatch_round_runs_nodes():
    g = AgentGraph()
    n = NodeState(template=AgentTemplate.PLANNER, branch_id="main")
    n.node_id = "planner1"
    g.add_node(n)

    llm = _make_mock_llm()
    store = ArtifactStore()
    bus = MessageBus(g)
    budget = BudgetWatchdog(BudgetConfig())

    dispatcher = Dispatcher(g, llm, store, bus, budget, task_summary="test task")
    results = await dispatcher.dispatch_round(0)

    assert "planner1" in results
    assert len(results["planner1"]) == 1  # One artifact produced
    assert n.status == NodeStatus.DONE


@pytest.mark.asyncio
async def test_dispatch_respects_dependencies():
    g = AgentGraph()
    a = NodeState(template=AgentTemplate.PLANNER, branch_id="main")
    a.node_id = "a"
    b = NodeState(template=AgentTemplate.CODER, branch_id="main")
    b.node_id = "b"
    g.add_node(a)
    g.add_node(b)
    g.add_edge(EdgeState(source="a", target="b"))

    # Mock LLM returns different results per template
    llm = _make_mock_llm()
    coder_response = LLMResponse(
        content='{"patches": [], "confidence": 0.8}',
        parsed={"patches": [], "confidence": 0.8},
        input_tokens=100,
        output_tokens=50,
    )
    planner_response = LLMResponse(
        content='{"sub_tasks": [], "strategy": "plan"}',
        parsed={"sub_tasks": [], "strategy": "plan"},
        input_tokens=100,
        output_tokens=50,
    )
    llm.call = AsyncMock(side_effect=[planner_response, coder_response])

    store = ArtifactStore()
    bus = MessageBus(g)
    budget = BudgetWatchdog(BudgetConfig())

    dispatcher = Dispatcher(g, llm, store, bus, budget, task_summary="test")
    results = await dispatcher.dispatch_round(0)

    assert "a" in results
    assert "b" in results
    assert a.status == NodeStatus.DONE
    assert b.status == NodeStatus.DONE
