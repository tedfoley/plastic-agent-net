"""Heuristic spawn triggers for the plasticity controller."""

from __future__ import annotations

from plastic_agent_net.config.defaults import ESCALATION_FAILURE_COUNT, SPAWN_UNCERTAINTY_THRESHOLD
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.models import (
    ActionType,
    AgentTemplate,
    ArtifactType,
    ControllerAction,
    ModelTier,
)
from plastic_agent_net.memory.artifact_store import ArtifactStore


def check_spawn_triggers(
    graph: AgentGraph,
    artifact_store: ArtifactStore,
    current_round: int,
) -> list[ControllerAction]:
    """Evaluate whether new nodes should be spawned."""
    actions: list[ControllerAction] = []

    # Check plans for uncertainty flags
    plans = artifact_store.list_by_type(ArtifactType.PLAN)
    for plan in plans:
        uncertainties = plan.content.get("uncertainties", [])
        if len(uncertainties) > 0:
            # Spawn an additional coder on a new branch for uncertain areas
            if plan.content.get("needs_branching"):
                actions.append(ControllerAction(
                    action_type=ActionType.SPAWN,
                    payload={
                        "template": AgentTemplate.CODER.value,
                        "branch_id": f"branch_{current_round}",
                        "reason": "uncertainty_branching",
                    },
                    reason=f"Plan has {len(uncertainties)} uncertainties, spawning alternative branch",
                ))

    # Check for repeated failures → spawn debugger
    verifications = artifact_store.list_by_type(ArtifactType.VERIFICATION)
    branch_failures: dict[str, int] = {}
    for v in verifications:
        if not v.content.get("tests_passed", True) or not v.content.get("build_passed", True):
            branch_failures[v.branch_id] = branch_failures.get(v.branch_id, 0) + 1

    for branch_id, count in branch_failures.items():
        if count >= ESCALATION_FAILURE_COUNT:
            # Check if debugger already exists on this branch
            has_debugger = any(
                n.template == AgentTemplate.DEBUGGER
                for n in graph.nodes_by_branch(branch_id)
            )
            if not has_debugger:
                actions.append(ControllerAction(
                    action_type=ActionType.SPAWN,
                    payload={
                        "template": AgentTemplate.DEBUGGER.value,
                        "branch_id": branch_id,
                    },
                    reason=f"Branch {branch_id} has {count} verification failures",
                ))

    # Check if patches exist without reviews
    patches = artifact_store.list_by_type(ArtifactType.PATCH)
    reviews = artifact_store.list_by_type(ArtifactType.REVIEW)
    reviewed_branches = {r.branch_id for r in reviews}
    for patch in patches:
        if patch.branch_id not in reviewed_branches:
            has_reviewer = any(
                n.template in (AgentTemplate.SKEPTIC_REVIEWER, AgentTemplate.SECURITY_REVIEWER)
                for n in graph.nodes_by_branch(patch.branch_id)
            )
            if not has_reviewer:
                actions.append(ControllerAction(
                    action_type=ActionType.SPAWN,
                    payload={
                        "template": AgentTemplate.SKEPTIC_REVIEWER.value,
                        "branch_id": patch.branch_id,
                    },
                    reason=f"Patch on branch {patch.branch_id} has no review",
                ))

    return actions
