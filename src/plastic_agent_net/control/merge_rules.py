"""Heuristic merge triggers for the plasticity controller."""

from __future__ import annotations

from plastic_agent_net.config.defaults import MERGE_SIMILARITY_THRESHOLD
from plastic_agent_net.control.scoring import compute_branch_score
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import ActionType, ArtifactType, ControllerAction
from plastic_agent_net.memory.artifact_store import ArtifactStore


def check_merge_triggers(
    graph: AgentGraph,
    artifact_store: ArtifactStore,
    current_round: int,
) -> list[ControllerAction]:
    """Evaluate whether branches should be merged."""
    actions: list[ControllerAction] = []
    branch_ids = list(graph.branch_ids())

    if len(branch_ids) < 2:
        return actions

    # Check for near-duplicate branches (similar patches targeting same files)
    branch_patches: dict[str, set[str]] = {}
    for bid in branch_ids:
        patches = [a for a in artifact_store.list_by_branch(bid) if a.artifact_type == ArtifactType.PATCH]
        files = set()
        for p in patches:
            for patch in p.content.get("patches", []):
                files.add(patch.get("file_path", ""))
        branch_patches[bid] = files

    checked: set[tuple[str, str]] = set()
    for b1 in branch_ids:
        for b2 in branch_ids:
            if b1 >= b2 or (b1, b2) in checked:
                continue
            checked.add((b1, b2))

            files1 = branch_patches.get(b1, set())
            files2 = branch_patches.get(b2, set())
            if not files1 or not files2:
                continue

            overlap = len(files1 & files2) / max(1, len(files1 | files2))
            if overlap >= MERGE_SIMILARITY_THRESHOLD:
                # Merge weaker into stronger
                score1 = compute_branch_score(b1, graph, artifact_store, current_round)
                score2 = compute_branch_score(b2, graph, artifact_store, current_round)

                winner, loser = (b1, b2) if score1 >= score2 else (b2, b1)
                actions.append(ControllerAction(
                    action_type=ActionType.MERGE,
                    payload={
                        "source_branch": loser,
                        "target_branch": winner,
                        "overlap": overlap,
                    },
                    reason=f"Branches {loser}→{winner} overlap {overlap:.0%}",
                ))

    # Check for converged branches (both passing verification with high scores)
    for bid in branch_ids:
        if bid == "main":
            continue
        score = compute_branch_score(bid, graph, artifact_store, current_round)
        main_score = compute_branch_score("main", graph, artifact_store, current_round)
        if score > 0.8 and main_score > 0.8 and current_round > 5:
            actions.append(ControllerAction(
                action_type=ActionType.MERGE,
                payload={
                    "source_branch": bid,
                    "target_branch": "main",
                    "convergence": True,
                },
                reason=f"Branch {bid} converged with main (both > 0.8)",
            ))

    return actions
