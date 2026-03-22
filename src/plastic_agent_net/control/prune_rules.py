"""Heuristic prune triggers for the plasticity controller."""

from __future__ import annotations

from plastic_agent_net.config.defaults import PRUNE_CONTRIBUTION_THRESHOLD
from plastic_agent_net.control.scoring import compute_branch_score, compute_node_contribution
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import ActionType, ControllerAction, NodeStatus
from plastic_agent_net.memory.artifact_store import ArtifactStore


def check_prune_triggers(
    graph: AgentGraph,
    artifact_store: ArtifactStore,
    current_round: int,
    budget_pressure: float,
) -> list[ControllerAction]:
    """Evaluate whether nodes or branches should be pruned."""
    actions: list[ControllerAction] = []

    # Prune individual nodes with low contribution
    for node in graph.active_nodes():
        if node.rounds_active < 2:
            continue  # Give nodes time to contribute

        contrib = compute_node_contribution(node, graph, artifact_store, current_round)
        node.contribution_score = contrib

        threshold = PRUNE_CONTRIBUTION_THRESHOLD
        if budget_pressure > 0.7:
            threshold *= 2  # More aggressive pruning under budget pressure

        if contrib < threshold:
            actions.append(ControllerAction(
                action_type=ActionType.PRUNE,
                target_node=node.node_id,
                reason=f"Low contribution ({contrib:.2f} < {threshold:.2f})",
            ))

    # Prune entire branches that are dominated
    branch_ids = list(graph.branch_ids())
    if len(branch_ids) > 1:
        branch_scores = {
            bid: compute_branch_score(bid, graph, artifact_store, current_round)
            for bid in branch_ids
        }
        if branch_scores:
            best_score = max(branch_scores.values())
            for bid, score in branch_scores.items():
                if bid == "main":
                    continue
                if score < best_score * 0.3 and current_round > 3:
                    for node in graph.nodes_by_branch(bid):
                        if node.status in (NodeStatus.PENDING, NodeStatus.RUNNING):
                            actions.append(ControllerAction(
                                action_type=ActionType.PRUNE,
                                target_node=node.node_id,
                                reason=f"Branch {bid} dominated (score {score:.2f} vs best {best_score:.2f})",
                            ))

    return actions
