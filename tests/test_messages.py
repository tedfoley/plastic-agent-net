"""Tests for MessageBus."""

from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.messages import MessageBus
from plastic_agent_net.core.models import EdgeState, Message, MessageType, NodeState


def _setup():
    g = AgentGraph()
    a = NodeState()
    a.node_id = "a"
    b = NodeState()
    b.node_id = "b"
    g.add_node(a)
    g.add_node(b)
    g.add_edge(EdgeState(source="a", target="b"))
    bus = MessageBus(g)
    return g, bus


def test_send_receive():
    _, bus = _setup()
    msg = Message(message_type=MessageType.TASK_ASSIGNMENT, sender="a", receiver="b", round_sent=0)
    assert bus.send(msg) is True
    received = bus.receive("b", current_round=0)
    assert len(received) == 1
    assert received[0].message_type == MessageType.TASK_ASSIGNMENT


def test_send_no_edge():
    _, bus = _setup()
    msg = Message(message_type=MessageType.TASK_ASSIGNMENT, sender="b", receiver="a", round_sent=0)
    assert bus.send(msg) is False


def test_receive_clears_inbox():
    _, bus = _setup()
    msg = Message(message_type=MessageType.TASK_ASSIGNMENT, sender="a", receiver="b", round_sent=0)
    bus.send(msg)
    bus.receive("b", current_round=0)
    assert bus.receive("b", current_round=0) == []


def test_ttl_expiry():
    _, bus = _setup()
    msg = Message(message_type=MessageType.TASK_ASSIGNMENT, sender="a", receiver="b", round_sent=0, ttl=2)
    bus.send(msg)
    # Round 0 + ttl 2 → expires after round 1
    received = bus.receive("b", current_round=5)
    assert len(received) == 0


def test_peek():
    _, bus = _setup()
    msg = Message(message_type=MessageType.FEEDBACK, sender="a", receiver="b", round_sent=0)
    bus.send(msg)
    peeked = bus.peek("b")
    assert len(peeked) == 1
    # Peek doesn't consume
    assert len(bus.peek("b")) == 1


def test_broadcast():
    g = AgentGraph()
    for nid in ["a", "b", "c"]:
        n = NodeState()
        n.node_id = nid
        g.add_node(n)
    g.add_edge(EdgeState(source="a", target="b"))
    g.add_edge(EdgeState(source="a", target="c"))
    bus = MessageBus(g)

    count = bus.send_broadcast("a", MessageType.STATUS_UPDATE, {"status": "done"}, round_num=0)
    assert count == 2


def test_history():
    _, bus = _setup()
    msg = Message(message_type=MessageType.TASK_ASSIGNMENT, sender="a", receiver="b")
    bus.send(msg)
    assert len(bus.history()) == 1
