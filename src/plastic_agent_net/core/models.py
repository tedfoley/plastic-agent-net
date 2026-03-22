"""All dataclasses for PlasticAgentNet graph state."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class AgentTemplate(str, Enum):
    PLANNER = "planner"
    REPO_MAPPER = "repo_mapper"
    CODER = "coder"
    VERIFIER_COORDINATOR = "verifier_coordinator"
    DEBUGGER = "debugger"
    TEST_WRITER = "test_writer"
    SKEPTIC_REVIEWER = "skeptic_reviewer"
    SECURITY_REVIEWER = "security_reviewer"
    REGRESSION_REVIEWER = "regression_reviewer"
    SYNTHESIZER = "synthesizer"


class ModelTier(str, Enum):
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"


class ArtifactType(str, Enum):
    PLAN = "plan"
    REPO_MAP = "repo_map"
    PATCH = "patch"
    TEST_CODE = "test_code"
    REVIEW = "review"
    DEBUG_REPORT = "debug_report"
    VERIFICATION = "verification"
    SYNTHESIS = "synthesis"
    TASK_PROFILE = "task_profile"


class MessageType(str, Enum):
    TASK_ASSIGNMENT = "task_assignment"
    ARTIFACT_REF = "artifact_ref"
    FEEDBACK = "feedback"
    ESCALATION = "escalation"
    STATUS_UPDATE = "status_update"


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    PRUNED = "pruned"
    MERGED = "merged"


class ActionType(str, Enum):
    SPAWN = "spawn"
    PRUNE = "prune"
    MERGE = "merge"
    ESCALATE = "escalate"
    REWEIGHT_EDGE = "reweight_edge"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"


@dataclass
class PersonaVector:
    """Soft personality dimensions that condition agent behavior."""
    caution: float = 0.5       # 0=bold, 1=conservative
    verbosity: float = 0.5     # 0=terse, 1=detailed
    creativity: float = 0.5    # 0=conventional, 1=exploratory
    skepticism: float = 0.5    # 0=trusting, 1=adversarial

    def render(self) -> str:
        traits = []
        if self.caution > 0.7:
            traits.append("You are cautious and conservative — prefer safe, well-tested approaches.")
        elif self.caution < 0.3:
            traits.append("You are bold — willing to try unconventional approaches when justified.")
        if self.verbosity > 0.7:
            traits.append("Be thorough and detailed in your explanations.")
        elif self.verbosity < 0.3:
            traits.append("Be concise — minimal explanation, focus on output.")
        if self.creativity > 0.7:
            traits.append("Think creatively — consider novel solutions beyond the obvious.")
        elif self.creativity < 0.3:
            traits.append("Stick to conventional, well-known patterns.")
        if self.skepticism > 0.7:
            traits.append("Be highly skeptical — question assumptions, look for flaws.")
        elif self.skepticism < 0.3:
            traits.append("Be constructive and trust the work of other agents.")
        return " ".join(traits) if traits else "Balanced approach across all dimensions."


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class NodeState:
    node_id: str = field(default_factory=_new_id)
    template: AgentTemplate = AgentTemplate.CODER
    persona: PersonaVector = field(default_factory=PersonaVector)
    model_tier: ModelTier = ModelTier.HAIKU
    branch_id: str = "main"
    status: NodeStatus = NodeStatus.PENDING
    round_created: int = 0
    rounds_active: int = 0
    tokens_used: int = 0
    contribution_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EdgeState:
    source: str  # node_id
    target: str  # node_id
    weight: float = 1.0
    message_types: list[MessageType] = field(default_factory=lambda: list(MessageType))
    active: bool = True


@dataclass
class Artifact:
    artifact_id: str = field(default_factory=_new_id)
    artifact_type: ArtifactType = ArtifactType.PATCH
    producer_node: str = ""
    branch_id: str = "main"
    round_produced: int = 0
    content: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(tz=None))


@dataclass
class Message:
    message_id: str = field(default_factory=_new_id)
    message_type: MessageType = MessageType.TASK_ASSIGNMENT
    sender: str = ""    # node_id
    receiver: str = ""  # node_id
    payload: dict[str, Any] = field(default_factory=dict)
    round_sent: int = 0
    ttl: int = 3  # rounds until expiry


@dataclass
class TaskProfile:
    raw_request: str = ""
    repo_path: str = ""
    task_type: str = "bugfix"  # bugfix, feature, refactor, test, docs
    estimated_complexity: str = "medium"  # low, medium, high
    candidate_files: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphState:
    nodes: dict[str, NodeState] = field(default_factory=dict)
    edges: list[EdgeState] = field(default_factory=list)
    current_round: int = 0


@dataclass
class ControllerAction:
    action_type: ActionType
    target_node: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


@dataclass
class ControllerState:
    round: int = 0
    actions_taken: list[ControllerAction] = field(default_factory=list)
    branch_scores: dict[str, float] = field(default_factory=dict)
    node_contributions: dict[str, float] = field(default_factory=dict)


@dataclass
class BudgetConfig:
    max_total_tokens: int = 500_000
    max_round_tokens: int = 100_000
    max_rounds: int = 20
    max_nodes: int = 15
    max_edges: int = 40
    max_branches: int = 4
    max_wall_seconds: float = 600.0


@dataclass
class BudgetUsage:
    total_tokens: int = 0
    round_tokens: int = 0
    rounds_completed: int = 0
    active_nodes: int = 0
    active_edges: int = 0
    active_branches: int = 0
    start_time: float = 0.0
