"""Tests for scoring functions."""

from plastic_agent_net.control.scoring import compute_branch_score, compute_node_contribution
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import Artifact, ArtifactType, EdgeState, NodeState
from plastic_agent_net.memory.artifact_store import ArtifactStore


def _setup():
    g = AgentGraph()
    store = ArtifactStore()
    n = NodeState()
    n.node_id = "n1"
    n.branch_id = "main"
    g.add_node(n)
    return g, store, n


def test_node_contribution_no_artifacts():
    g, store, n = _setup()
    score = compute_node_contribution(n, g, store, current_round=0)
    assert score == 0.0


def test_node_contribution_with_artifacts():
    g, store, n = _setup()
    store.put(Artifact(
        artifact_type=ArtifactType.PATCH,
        producer_node="n1",
        branch_id="main",
        round_produced=0,
    ))
    score = compute_node_contribution(n, g, store, current_round=0)
    assert score > 0


def test_node_contribution_with_verification():
    g, store, n = _setup()
    store.put(Artifact(
        artifact_type=ArtifactType.PATCH,
        producer_node="n1",
        branch_id="main",
    ))
    store.put(Artifact(
        artifact_type=ArtifactType.VERIFICATION,
        producer_node="v1",
        branch_id="main",
        round_produced=0,
        content={"overall_score": 0.5},
    ))
    store.put(Artifact(
        artifact_type=ArtifactType.VERIFICATION,
        producer_node="v1",
        branch_id="main",
        round_produced=1,
        content={"overall_score": 0.8},
    ))
    score = compute_node_contribution(n, g, store, current_round=1)
    assert score > 0


def test_branch_score_no_verifications():
    g, store, n = _setup()
    score = compute_branch_score("main", g, store, current_round=0)
    assert score == 0.0


def test_branch_score_with_verification():
    g, store, n = _setup()
    store.put(Artifact(
        artifact_type=ArtifactType.VERIFICATION,
        branch_id="main",
        round_produced=0,
        content={"overall_score": 0.7},
    ))
    score = compute_branch_score("main", g, store, current_round=0)
    assert score > 0.4  # 0.7 * 0.7 = 0.49 minimum
