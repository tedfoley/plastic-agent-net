"""Episode: full task lifecycle from init through dispatch loop to output."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

from plastic_agent_net.config.defaults import DEFAULT_BUDGET
from plastic_agent_net.config.templates import TEMPLATE_CONFIGS
from plastic_agent_net.control.controller import PlasticityController
from plastic_agent_net.core.budgets import BudgetExceeded, BudgetWatchdog
from plastic_agent_net.core.graph import AgentGraph
from plastic_agent_net.core.messages import MessageBus
from plastic_agent_net.core.models import (
    AgentTemplate,
    BudgetConfig,
    ControllerState,
    EdgeState,
    ModelTier,
    NodeState,
    NodeStatus,
)
from plastic_agent_net.llm.client import AnthropicClient
from plastic_agent_net.memory.artifact_store import ArtifactStore
from plastic_agent_net.memory.memory_manager import MemoryManager
from plastic_agent_net.runtime.dispatcher import Dispatcher
from plastic_agent_net.runtime.task_encoder import TaskEncoder
from plastic_agent_net.runtime.verifier import Verifier
from plastic_agent_net.tools.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass
class EpisodeResult:
    task_summary: str = ""
    rounds_completed: int = 0
    final_artifacts: list[dict[str, Any]] = field(default_factory=list)
    branch_scores: dict[str, float] = field(default_factory=dict)
    tokens_used: int = 0
    terminated_reason: str = ""


class Episode:
    """Manages the full lifecycle of a coding task."""

    def __init__(
        self,
        llm: AnthropicClient,
        repo_path: str = "",
        budget_config: BudgetConfig | None = None,
        event_callback: Callable[[dict], None] | None = None,
        supabase_repo: Any | None = None,
    ) -> None:
        self._llm = llm
        self._repo_path = repo_path
        self._budget = BudgetWatchdog(budget_config or DEFAULT_BUDGET)
        self._graph = AgentGraph()
        self._artifact_store = ArtifactStore()
        self._message_bus = MessageBus(self._graph)
        self._memory = MemoryManager()
        self._workspace_manager = WorkspaceManager(repo_path if repo_path else None)
        self._verifier = Verifier(self._workspace_manager, self._artifact_store)
        self._controller = PlasticityController(
            self._graph, self._artifact_store, self._message_bus, self._budget
        )
        self._event_cb = event_callback
        self._supabase_repo = supabase_repo
        self._episode_id: str | None = None

    async def run(self, user_request: str) -> EpisodeResult:
        """Execute a full episode: encode → seed → loop → output."""
        result = EpisodeResult(task_summary=user_request)

        # Create Supabase episode record if connected
        if self._supabase_repo:
            self._episode_id = self._supabase_repo.create_episode(
                task=user_request,
                repo_path=self._repo_path,
                budget_config=self._budget.config,
            )
            self._supabase_repo.update_episode(self._episode_id, status="running")

        try:
            # 1. Encode the task
            encoder = TaskEncoder(self._llm)
            task_profile = await encoder.encode(user_request, self._repo_path)
            self._emit({"event": "task_encoded", "profile": task_profile.__dict__})

            # 2. Build seed graph
            self._build_seed_graph(task_profile.raw_request)
            self._sync_to_supabase()

            # 3. Create workspace for main branch
            await self._workspace_manager.create("main")

            # 4. Main loop
            dispatcher = Dispatcher(
                graph=self._graph,
                llm=self._llm,
                artifact_store=self._artifact_store,
                message_bus=self._message_bus,
                budget=self._budget,
                task_summary=user_request,
                repo_path=self._repo_path,
            )

            while self._budget.remaining_rounds() > 0:
                current_round = self._budget.usage.rounds_completed
                self._emit({"event": "round_start", "round": current_round})

                # Dispatch agents
                round_results = await dispatcher.dispatch_round(current_round)
                self._emit({
                    "event": "round_dispatched",
                    "round": current_round,
                    "nodes_run": len(round_results),
                })

                # Verify branches
                for branch_id in self._graph.branch_ids():
                    try:
                        verif = await self._verifier.evaluate_branch(branch_id, current_round)
                        self._emit({
                            "event": "verification",
                            "branch": branch_id,
                            "score": verif.overall_score,
                            "issues": len(verif.blocking_issues),
                        })
                    except Exception as verif_err:
                        logger.warning("Verification failed for branch %s: %s", branch_id, verif_err)
                        self._emit({
                            "event": "verification",
                            "branch": branch_id,
                            "score": 0.0,
                            "issues": 1,
                            "error": str(verif_err),
                        })

                # Controller step
                ctrl_state = self._controller.step(current_round)
                self._emit({
                    "event": "controller_step",
                    "round": current_round,
                    "actions": len(ctrl_state.actions_taken),
                    "branch_scores": ctrl_state.branch_scores,
                })

                # Write-behind: sync state to Supabase after each round
                self._sync_to_supabase(current_round, ctrl_state)

                self._budget.new_round()

                # Check convergence
                if self._check_convergence(ctrl_state):
                    result.terminated_reason = "converged"
                    break

                # Check for manual pause/fail from dashboard
                if await self._check_manual_stop():
                    result.terminated_reason = "manually_stopped"
                    break

                # Reset pending nodes for next round
                self._reset_done_nodes()

            else:
                result.terminated_reason = "budget_rounds"

        except BudgetExceeded as e:
            result.terminated_reason = f"budget_{e.resource}"
            logger.warning("Episode terminated: %s", e)
        except Exception as e:
            result.terminated_reason = f"error: {e}"
            logger.exception("Episode failed")
        finally:
            await self._workspace_manager.cleanup_all()

            # Gather final results
            result.rounds_completed = self._budget.usage.rounds_completed
            result.tokens_used = self._budget.usage.total_tokens
            result.final_artifacts = [
                {
                    "id": a.artifact_id,
                    "type": a.artifact_type.value,
                    "branch": a.branch_id,
                    "summary": a.summary,
                    "content": a.content,
                }
                for a in self._artifact_store.list_all()
            ]
            result.branch_scores = dict(self._controller._state.branch_scores)

            # Finalize Supabase episode — inside finally so it always runs
            if self._supabase_repo and self._episode_id:
                try:
                    # Don't overwrite manually-set statuses (paused/failed from dashboard)
                    if result.terminated_reason == "manually_stopped":
                        # Status already set by dashboard; just update counters
                        self._supabase_repo.update_episode(
                            self._episode_id,
                            rounds_completed=result.rounds_completed,
                            tokens_used=result.tokens_used,
                            branch_scores=result.branch_scores,
                            terminated_reason=result.terminated_reason,
                        )
                    else:
                        self._supabase_repo.update_episode(
                            self._episode_id,
                            status="completed" if "error" not in result.terminated_reason else "failed",
                            rounds_completed=result.rounds_completed,
                            tokens_used=result.tokens_used,
                            branch_scores=result.branch_scores,
                            terminated_reason=result.terminated_reason,
                        )
                except Exception:
                    logger.warning("Failed to finalize episode in Supabase", exc_info=True)

        self._emit({"event": "episode_complete", "result": result.__dict__})
        return result

    def _build_seed_graph(self, task_summary: str) -> None:
        """Create the initial graph topology."""
        # Planner node
        planner_cfg = TEMPLATE_CONFIGS[AgentTemplate.PLANNER]
        planner = NodeState(
            template=AgentTemplate.PLANNER,
            persona=planner_cfg.persona_prior,
            model_tier=planner_cfg.default_model_tier,
            branch_id="main",
        )
        self._graph.add_node(planner)

        # RepoMapper node
        mapper_cfg = TEMPLATE_CONFIGS[AgentTemplate.REPO_MAPPER]
        mapper = NodeState(
            template=AgentTemplate.REPO_MAPPER,
            persona=mapper_cfg.persona_prior,
            model_tier=mapper_cfg.default_model_tier,
            branch_id="main",
        )
        self._graph.add_node(mapper)

        # Coder node
        coder_cfg = TEMPLATE_CONFIGS[AgentTemplate.CODER]
        coder = NodeState(
            template=AgentTemplate.CODER,
            persona=coder_cfg.persona_prior,
            model_tier=coder_cfg.default_model_tier,
            branch_id="main",
        )
        self._graph.add_node(coder)

        # Verifier coordinator
        verifier_cfg = TEMPLATE_CONFIGS[AgentTemplate.VERIFIER_COORDINATOR]
        verifier = NodeState(
            template=AgentTemplate.VERIFIER_COORDINATOR,
            persona=verifier_cfg.persona_prior,
            model_tier=verifier_cfg.default_model_tier,
            branch_id="main",
        )
        self._graph.add_node(verifier)

        # Edges: planner→coder, mapper→coder, coder→verifier
        self._graph.add_edge(EdgeState(source=planner.node_id, target=coder.node_id))
        self._graph.add_edge(EdgeState(source=mapper.node_id, target=coder.node_id))
        self._graph.add_edge(EdgeState(source=coder.node_id, target=verifier.node_id))

        logger.info("Seed graph: 4 nodes, 3 edges")

    def _check_convergence(self, ctrl_state: ControllerState) -> bool:
        """Check if the episode has converged (high score, no actions needed)."""
        if not ctrl_state.branch_scores:
            return False
        best_score = max(ctrl_state.branch_scores.values())
        no_actions = len(ctrl_state.actions_taken) == 0
        return best_score >= 0.9 and no_actions

    async def _check_manual_stop(self) -> bool:
        """Check if the episode was paused or failed from the dashboard."""
        if not self._supabase_repo or not self._episode_id:
            return False
        try:
            ep = self._supabase_repo.get_episode(self._episode_id)
            if ep and ep.get("status") in ("paused", "failed"):
                logger.info("Episode manually stopped via dashboard: %s", ep["status"])
                return True
        except Exception:
            pass
        return False

    def _reset_done_nodes(self) -> None:
        """Reset DONE nodes back to PENDING for the next round."""
        for node in self._graph.all_nodes():
            if node.status == NodeStatus.DONE:
                node.status = NodeStatus.PENDING

    def _sync_to_supabase(
        self, current_round: int | None = None, ctrl_state: ControllerState | None = None
    ) -> None:
        """Write-behind: persist current state to Supabase after each round."""
        if not self._supabase_repo or not self._episode_id:
            return
        try:
            self._supabase_repo.sync_graph_state(
                self._episode_id,
                self._graph.all_nodes(),
                self._graph.all_edges(),
            )
            self._supabase_repo.sync_artifacts(
                self._episode_id,
                self._artifact_store.list_all(),
            )
            if current_round is not None:
                self._supabase_repo.update_episode(
                    self._episode_id,
                    rounds_completed=current_round + 1,
                    tokens_used=self._budget.usage.total_tokens,
                    branch_scores=dict(ctrl_state.branch_scores) if ctrl_state else {},
                )
            if ctrl_state:
                for action in ctrl_state.actions_taken:
                    self._supabase_repo.insert_controller_action(
                        self._episode_id, action, current_round or 0
                    )
        except Exception:
            logger.warning("Failed to sync to Supabase", exc_info=True)

    def _emit(self, event: dict) -> None:
        if self._event_cb:
            self._event_cb(event)

        # Persist event to Supabase for dashboard Live Log
        if self._supabase_repo and self._episode_id:
            try:
                event_type = event.get("event", "unknown")
                round_num = event.get("round")
                # Store the full event dict as payload, excluding the 'event' key
                # Convert values to JSON-safe types
                payload = {}
                for k, v in event.items():
                    if k == "event":
                        continue
                    try:
                        import json
                        json.dumps(v)
                        payload[k] = v
                    except (TypeError, ValueError):
                        payload[k] = str(v)
                self._supabase_repo.insert_event(
                    self._episode_id, event_type, round_num, payload
                )
            except Exception:
                logger.debug("Failed to persist event to Supabase", exc_info=True)

    # Expose internals for dashboard/testing
    @property
    def graph(self) -> AgentGraph:
        return self._graph

    @property
    def artifact_store(self) -> ArtifactStore:
        return self._artifact_store

    @property
    def budget(self) -> BudgetWatchdog:
        return self._budget
