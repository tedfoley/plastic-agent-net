"""Node contribution and branch scoring functions."""

from __future__ import annotations

from plastic_agent_net.config.defaults import SCORING_WEIGHTS
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import ArtifactType, NodeState
from plastic_agent_net.memory.artifact_store import ArtifactStore


def compute_node_contribution(
    node: NodeState,
    graph: AgentGraph,
    artifact_store: ArtifactStore,
    current_round: int,
) -> float:
    """Score a node's contribution based on artifact output and novelty."""
    artifacts = artifact_store.list_by_producer(node.node_id)
    if not artifacts:
        return 0.0

    w = SCORING_WEIGHTS
    score = 0.0

    # Novelty: how many unique artifact types produced
    types_produced = {a.artifact_type for a in artifacts}
    score += w["novelty"] * min(1.0, len(types_produced) / 3)

    # Verification delta: did verification scores improve after this node's artifacts?
    verifications = artifact_store.list_by_type(ArtifactType.VERIFICATION)
    branch_verifs = [v for v in verifications if v.branch_id == node.branch_id]
    if len(branch_verifs) >= 2:
        recent = sorted(branch_verifs, key=lambda v: v.round_produced)
        prev_score = recent[-2].content.get("overall_score", 0)
        curr_score = recent[-1].content.get("overall_score", 0)
        delta = max(0, curr_score - prev_score)
        score += w["verification_delta"] * delta
    elif branch_verifs:
        score += w["verification_delta"] * branch_verifs[-1].content.get("overall_score", 0)

    # Peer agreement: how many successors consumed this node's output
    successors = graph.successors(node.node_id)
    if successors:
        active_successors = sum(
            1 for s in successors if graph.get_node(s) and graph.get_node(s).status.value in ("running", "done")
        )
        score += w["peer_agreement"] * min(1.0, active_successors / max(1, len(successors)))

    # Recency penalty: older nodes contribute less
    age = current_round - node.round_created
    recency = max(0, 1.0 - age / 10)
    score += w["recency"] * recency

    return min(1.0, score)


def compute_branch_score(
    branch_id: str,
    graph: AgentGraph,
    artifact_store: ArtifactStore,
    current_round: int,
) -> float:
    """Score a branch based on verification results and node contributions."""
    # Latest verification score
    verifications = [
        a for a in artifact_store.list_by_type(ArtifactType.VERIFICATION)
        if a.branch_id == branch_id
    ]
    verif_score = 0.0
    if verifications:
        latest = max(verifications, key=lambda v: v.round_produced)
        verif_score = latest.content.get("overall_score", 0.0)

    # Average node contribution
    branch_nodes = graph.nodes_by_branch(branch_id)
    if branch_nodes:
        contrib_scores = [
            compute_node_contribution(n, graph, artifact_store, current_round)
            for n in branch_nodes
        ]
        avg_contrib = sum(contrib_scores) / len(contrib_scores)
    else:
        avg_contrib = 0.0

    return 0.7 * verif_score + 0.3 * avg_contrib
