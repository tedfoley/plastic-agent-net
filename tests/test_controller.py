"""Tests for PlasticityController."""

from plastic_agent_net.control.controller import PlasticityController
from plastic_agent_net.core.budgets import BudgetWatchdog
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.messages import MessageBus
from plastic_agent_net.core.models import (
    AgentTemplate,
    Artifact,
    ArtifactType,
    BudgetConfig,
    EdgeState,
    NodeState,
)
from plastic_agent_net.memory.artifact_store import ArtifactStore


def _setup():
    g = AgentGraph()
    store = ArtifactStore()
    bus = MessageBus(g)
    budget = BudgetWatchdog(BudgetConfig(max_nodes=10, max_branches=4))
    ctrl = PlasticityController(g, store, bus, budget)
    return g, store, bus, budget, ctrl


def test_step_empty_graph():
    g, store, bus, budget, ctrl = _setup()
    state = ctrl.step(current_round=0)
    assert state.round == 0
    assert len(state.actions_taken) == 0


def test_step_spawns_reviewer_for_unreviewed_patch():
    g, store, bus, budget, ctrl = _setup()
    n = NodeState(template=AgentTemplate.CODER, branch_id="main")
    n.node_id = "coder1"
    g.add_node(n)

    store.put(Artifact(
        artifact_type=ArtifactType.PATCH,
        producer_node="coder1",
        branch_id="main",
    ))

    state = ctrl.step(current_round=1)
    spawn_actions = [a for a in state.actions_taken if a.action_type.value == "spawn"]
    assert len(spawn_actions) >= 1


def test_step_respects_node_budget():
    g, store, bus, _, ctrl = _setup()
    budget = BudgetWatchdog(BudgetConfig(max_nodes=1, max_branches=1))
    ctrl = PlasticityController(g, store, bus, budget)

    n = NodeState(template=AgentTemplate.CODER, branch_id="main")
    n.node_id = "coder1"
    g.add_node(n)

    store.put(Artifact(
        artifact_type=ArtifactType.PATCH,
        producer_node="coder1",
        branch_id="main",
    ))

    state = ctrl.step(current_round=1)
    # Should skip spawns due to node limit
    spawn_actions = [a for a in state.actions_taken if a.action_type.value == "spawn"]
    assert len(spawn_actions) == 0


def test_controller_updates_scores():
    g, store, bus, budget, ctrl = _setup()
    n = NodeState(template=AgentTemplate.CODER, branch_id="main")
    n.node_id = "n1"
    g.add_node(n)

    store.put(Artifact(
        artifact_type=ArtifactType.VERIFICATION,
        branch_id="main",
        content={"overall_score": 0.6},
    ))

    state = ctrl.step(current_round=0)
    assert "main" in state.branch_scores
