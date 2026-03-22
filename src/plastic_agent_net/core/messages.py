"""MessageBus: typed message routing along graph edges."""

from __future__ import annotations

from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import Message, MessageType


class MessageBus:
    """Routes typed messages between nodes along active edges."""

    def __init__(self, graph: AgentGraph) -> None:
        self._graph = graph
        self._inbox: dict[str, list[Message]] = {}  # node_id -> messages
        self._history: list[Message] = []

    def send(self, message: Message) -> bool:
        """Send a message along an active edge. Returns False if no valid edge exists."""
        edge = self._graph.get_edge(message.sender, message.receiver)
        if edge is None or not edge.active:
            return False
        if message.message_type not in edge.message_types:
            return False
        self._inbox.setdefault(message.receiver, []).append(message)
        self._history.append(message)
        return True

    def send_broadcast(self, sender: str, message_type: MessageType, payload: dict, round_num: int) -> int:
        """Broadcast to all successors. Returns count of messages sent."""
        sent = 0
        for target_id in self._graph.successors(sender):
            msg = Message(
                message_type=message_type,
                sender=sender,
                receiver=target_id,
                payload=payload,
                round_sent=round_num,
            )
            if self.send(msg):
                sent += 1
        return sent

    def receive(self, node_id: str, current_round: int) -> list[Message]:
        """Get all non-expired messages for a node, clearing inbox."""
        messages = self._inbox.pop(node_id, [])
        return [m for m in messages if current_round - m.round_sent < m.ttl]

    def peek(self, node_id: str) -> list[Message]:
        """Peek at pending messages without consuming."""
        return list(self._inbox.get(node_id, []))

    def history(self) -> list[Message]:
        return list(self._history)
