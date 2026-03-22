"""Tests for AgentGraph."""

from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import AgentTemplate, EdgeState, NodeState, NodeStatus


def _make_node(node_id: str = "", branch: str = "main", template: AgentTemplate = AgentTemplate.CODER) -> NodeState:
    n = NodeState(template=template, branch_id=branch)
    if node_id:
        n.node_id = node_id
    return n


def test_add_and_get_node():
    g = AgentGraph()
    n = _make_node("n1")
    g.add_node(n)
    assert g.get_node("n1") is n
    assert g.node_count() == 1


def test_remove_node():
    g = AgentGraph()
    n = _make_node("n1")
    g.add_node(n)
    g.remove_node("n1")
    assert n.status == NodeStatus.PRUNED
    assert g.node_count() == 0


def test_add_and_get_edge():
    g = AgentGraph()
    g.add_node(_make_node("a"))
    g.add_node(_make_node("b"))
    e = EdgeState(source="a", target="b")
    g.add_edge(e)
    assert g.get_edge("a", "b") is e
    assert g.edge_count() == 1


def test_remove_edge():
    g = AgentGraph()
    g.add_node(_make_node("a"))
    g.add_node(_make_node("b"))
    g.add_edge(EdgeState(source="a", target="b"))
    g.remove_edge("a", "b")
    assert g.get_edge("a", "b") is None
    assert g.edge_count() == 0


def test_successors_predecessors():
    g = AgentGraph()
    g.add_node(_make_node("a"))
    g.add_node(_make_node("b"))
    g.add_node(_make_node("c"))
    g.add_edge(EdgeState(source="a", target="b"))
    g.add_edge(EdgeState(source="a", target="c"))

    assert set(g.successors("a")) == {"b", "c"}
    assert g.predecessors("b") == ["a"]


def test_topological_waves():
    g = AgentGraph()
    g.add_node(_make_node("a"))
    g.add_node(_make_node("b"))
    g.add_node(_make_node("c"))
    g.add_edge(EdgeState(source="a", target="b"))
    g.add_edge(EdgeState(source="b", target="c"))

    waves = g.topological_waves()
    assert len(waves) == 3
    assert waves[0] == ["a"]
    assert waves[1] == ["b"]
    assert waves[2] == ["c"]


def test_topological_waves_parallel():
    g = AgentGraph()
    g.add_node(_make_node("root"))
    g.add_node(_make_node("a"))
    g.add_node(_make_node("b"))
    g.add_edge(EdgeState(source="root", target="a"))
    g.add_edge(EdgeState(source="root", target="b"))

    waves = g.topological_waves()
    assert len(waves) == 2
    assert waves[0] == ["root"]
    assert set(waves[1]) == {"a", "b"}


def test_nodes_by_branch():
    g = AgentGraph()
    g.add_node(_make_node("a", branch="main"))
    g.add_node(_make_node("b", branch="feat"))
    g.add_node(_make_node("c", branch="main"))

    main_nodes = g.nodes_by_branch("main")
    assert len(main_nodes) == 2


def test_branch_ids():
    g = AgentGraph()
    g.add_node(_make_node("a", branch="main"))
    g.add_node(_make_node("b", branch="feat"))
    assert g.branch_ids() == {"main", "feat"}


def test_snapshot():
    g = AgentGraph()
    g.add_node(_make_node("a"))
    g.add_edge(EdgeState(source="a", target="a"))
    snap = g.snapshot()
    assert "a" in snap.nodes
    assert len(snap.edges) == 1


def test_active_nodes_excludes_pruned():
    g = AgentGraph()
    n1 = _make_node("a")
    n2 = _make_node("b")
    g.add_node(n1)
    g.add_node(n2)
    n2.status = NodeStatus.PRUNED
    assert len(g.active_nodes()) == 1
