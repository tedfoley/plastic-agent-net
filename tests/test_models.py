"""Tests for core data models."""

from plastic_agent_net.core.models import (
    ActionType,
    AgentTemplate,
    Artifact,
    ArtifactType,
    BudgetConfig,
    ControllerAction,
    EdgeState,
    GraphState,
    Message,
    MessageType,
    ModelTier,
    NodeState,
    NodeStatus,
    PersonaVector,
    TaskProfile,
)


def test_persona_vector_defaults():
    p = PersonaVector()
    assert p.caution == 0.5
    assert p.verbosity == 0.5
    text = p.render()
    assert isinstance(text, str)


def test_persona_vector_extreme():
    p = PersonaVector(caution=0.9, verbosity=0.1, creativity=0.9, skepticism=0.1)
    text = p.render()
    assert "cautious" in text.lower() or "conservative" in text.lower()
    assert "concise" in text.lower() or "minimal" in text.lower()


def test_node_state_defaults():
    n = NodeState()
    assert len(n.node_id) == 12
    assert n.template == AgentTemplate.CODER
    assert n.status == NodeStatus.PENDING
    assert n.tokens_used == 0


def test_node_state_unique_ids():
    n1 = NodeState()
    n2 = NodeState()
    assert n1.node_id != n2.node_id


def test_edge_state():
    e = EdgeState(source="a", target="b")
    assert e.weight == 1.0
    assert e.active is True
    assert MessageType.TASK_ASSIGNMENT in e.message_types


def test_artifact():
    a = Artifact(artifact_type=ArtifactType.PATCH, producer_node="node1")
    assert a.artifact_type == ArtifactType.PATCH
    assert len(a.artifact_id) == 12


def test_message():
    m = Message(message_type=MessageType.FEEDBACK, sender="a", receiver="b")
    assert m.ttl == 3


def test_task_profile():
    tp = TaskProfile(raw_request="fix bug", repo_path="/tmp")
    assert tp.task_type == "bugfix"


def test_budget_config():
    bc = BudgetConfig()
    assert bc.max_total_tokens == 500_000
    assert bc.max_rounds == 20


def test_controller_action():
    ca = ControllerAction(action_type=ActionType.SPAWN, reason="test")
    assert ca.action_type == ActionType.SPAWN


def test_graph_state():
    gs = GraphState()
    assert len(gs.nodes) == 0
    assert len(gs.edges) == 0


def test_enums():
    assert AgentTemplate.PLANNER.value == "planner"
    assert ModelTier.HAIKU.value == "haiku"
    assert ArtifactType.PATCH.value == "patch"
    assert NodeStatus.RUNNING.value == "running"
    assert ActionType.MERGE.value == "merge"
