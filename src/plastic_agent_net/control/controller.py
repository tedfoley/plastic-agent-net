"""PlasticityController: orchestrate spawn/prune/merge/escalate."""

from __future__ import annotations

import logging
from typing import Any

from plastic_agent_net.config.templates import TEMPLATE_CONFIGS
from plastic_agent_net.control.merge_rules import check_merge_triggers
from plastic_agent_net.control.prune_rules import check_prune_triggers
from plastic_agent_net.control.scoring import compute_branch_score, compute_node_contribution
from plastic_agent_net.control.spawn_rules import check_spawn_triggers
from plastic_agent_net.core.budgets import BudgetWatchdog
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.messages import MessageBus
from plastic_agent_net.core.models import (
    ActionType,
    AgentTemplate,
    ControllerAction,
    ControllerState,
    EdgeState,
    ModelTier,
    NodeState,
    NodeStatus,
    PersonaVector,
)
from plastic_agent_net.memory.artifact_store import ArtifactStore

logger = logging.getLogger(__name__)


class PlasticityController:
    """Aggregates signals from rules and applies structural changes to the graph."""

    def __init__(
        self,
        graph: AgentGraph,
        artifact_store: ArtifactStore,
        message_bus: MessageBus,
        budget: BudgetWatchdog,
    ) -> None:
        self._graph = graph
        self._artifact_store = artifact_store
        self._message_bus = message_bus
        self._budget = budget
        self._state = ControllerState()

    def step(self, current_round: int) -> ControllerState:
        """One controller step: aggregate signals → compute actions → apply."""
        self._state = ControllerState(round=current_round)
        pressure = self._budget.pressure()

        # Gather actions from all rule sets
        actions: list[ControllerAction] = []
        actions.extend(check_spawn_triggers(self._graph, self._artifact_store, current_round))
        actions.extend(check_prune_triggers(self._graph, self._artifact_store, current_round, pressure))
        actions.extend(check_merge_triggers(self._graph, self._artifact_store, current_round))
        actions.extend(self._check_escalation(current_round))

        # Filter by budget constraints
        actions = self._filter_by_budget(actions)

        # Apply actions
        for action in actions:
            self._apply(action, current_round)
            self._state.actions_taken.append(action)

        # Update scores
        for bid in self._graph.branch_ids():
            self._state.branch_scores[bid] = compute_branch_score(
                bid, self._graph, self._artifact_store, current_round
            )
        for node in self._graph.active_nodes():
            self._state.node_contributions[node.node_id] = compute_node_contribution(
                node, self._graph, self._artifact_store, current_round
            )

        return self._state

    def _check_escalation(self, current_round: int) -> list[ControllerAction]:
        """Check if any nodes should be escalated to a stronger model."""
        actions = []
        for node in self._graph.active_nodes():
            if node.model_tier == ModelTier.OPUS:
                continue  # Already at max
            if node.rounds_active >= 3 and node.contribution_score < 0.2:
                template_config = TEMPLATE_CONFIGS.get(node.template)
                escalation_tier = template_config.escalation_tier if template_config else ModelTier.SONNET
                actions.append(ControllerAction(
                    action_type=ActionType.ESCALATE,
                    target_node=node.node_id,
                    payload={"new_tier": escalation_tier.value},
                    reason=f"Node {node.node_id} underperforming, escalating to {escalation_tier.value}",
                ))
        return actions

    def _filter_by_budget(self, actions: list[ControllerAction]) -> list[ControllerAction]:
        """Remove actions that would violate budget constraints."""
        filtered = []
        pending_spawns = 0

        for action in actions:
            if action.action_type == ActionType.SPAWN:
                if self._graph.node_count() + pending_spawns >= self._budget.config.max_nodes:
                    logger.info("Skipping spawn: at node limit")
                    continue
                new_branch = action.payload.get("branch_id", "main")
                if new_branch not in self._graph.branch_ids() and len(self._graph.branch_ids()) >= self._budget.config.max_branches:
                    logger.info("Skipping spawn: at branch limit")
                    continue
                pending_spawns += 1

            filtered.append(action)

        return filtered

    def _apply(self, action: ControllerAction, current_round: int) -> None:
        """Apply a single controller action to the graph."""
        if action.action_type == ActionType.SPAWN:
            self._apply_spawn(action, current_round)
        elif action.action_type == ActionType.PRUNE:
            self._apply_prune(action)
        elif action.action_type == ActionType.MERGE:
            self._apply_merge(action)
        elif action.action_type == ActionType.ESCALATE:
            self._apply_escalate(action)
        elif action.action_type == ActionType.REWEIGHT_EDGE:
            self._apply_reweight(action)
        elif action.action_type == ActionType.ADD_EDGE:
            self._apply_add_edge(action)
        elif action.action_type == ActionType.REMOVE_EDGE:
            self._apply_remove_edge(action)

    def _apply_spawn(self, action: ControllerAction, current_round: int) -> None:
        template_str = action.payload.get("template", "coder")
        template = AgentTemplate(template_str)
        branch_id = action.payload.get("branch_id", "main")
        config = TEMPLATE_CONFIGS.get(template)

        node = NodeState(
            template=template,
            persona=config.persona_prior if config else PersonaVector(),
            model_tier=config.default_model_tier if config else ModelTier.HAIKU,
            branch_id=branch_id,
            round_created=current_round,
        )
        self._graph.add_node(node)

        # Connect to existing nodes on same branch
        for existing in self._graph.nodes_by_branch(branch_id):
            if existing.node_id != node.node_id and existing.status != NodeStatus.PRUNED:
                self._graph.add_edge(EdgeState(source=existing.node_id, target=node.node_id))

        logger.info("Spawned %s node %s on branch %s", template.value, node.node_id, branch_id)

    def _apply_prune(self, action: ControllerAction) -> None:
        self._graph.remove_node(action.target_node)
        logger.info("Pruned node %s: %s", action.target_node, action.reason)

    def _apply_merge(self, action: ControllerAction) -> None:
        source_branch = action.payload.get("source_branch", "")
        target_branch = action.payload.get("target_branch", "main")

        for node in self._graph.nodes_by_branch(source_branch):
            node.status = NodeStatus.MERGED
            node.branch_id = target_branch

        logger.info("Merged branch %s into %s", source_branch, target_branch)

    def _apply_escalate(self, action: ControllerAction) -> None:
        node = self._graph.get_node(action.target_node)
        if node:
            new_tier = ModelTier(action.payload.get("new_tier", "sonnet"))
            node.model_tier = new_tier
            logger.info("Escalated node %s to %s", node.node_id, new_tier.value)

    def _apply_reweight(self, action: ControllerAction) -> None:
        source = action.payload.get("source", "")
        target = action.payload.get("target", "")
        weight = action.payload.get("weight", 1.0)
        edge = self._graph.get_edge(source, target)
        if edge:
            edge.weight = weight

    def _apply_add_edge(self, action: ControllerAction) -> None:
        source = action.payload.get("source", "")
        target = action.payload.get("target", "")
        self._graph.add_edge(EdgeState(source=source, target=target))

    def _apply_remove_edge(self, action: ControllerAction) -> None:
        source = action.payload.get("source", "")
        target = action.payload.get("target", "")
        self._graph.remove_edge(source, target)
