"""Default budgets, model configs, and system constants."""

from plastic_agent_net.core.models import BudgetConfig, ModelTier

# Model name mapping
MODEL_MAP: dict[ModelTier, str] = {
    ModelTier.HAIKU: "claude-haiku-4-5-20251001",
    ModelTier.SONNET: "claude-sonnet-4-6",
    ModelTier.OPUS: "claude-opus-4-6",
}

# Max tokens per tier
TIER_MAX_TOKENS: dict[ModelTier, int] = {
    ModelTier.HAIKU: 4096,
    ModelTier.SONNET: 8192,
    ModelTier.OPUS: 8192,
}

# Default budget
DEFAULT_BUDGET = BudgetConfig(
    max_total_tokens=500_000,
    max_round_tokens=100_000,
    max_rounds=20,
    max_nodes=15,
    max_edges=40,
    max_branches=4,
    max_wall_seconds=600.0,
)

# Dashboard
DASHBOARD_PORT = 8420
DASHBOARD_HOST = "0.0.0.0"

# Scoring weights
SCORING_WEIGHTS = {
    "novelty": 0.3,
    "verification_delta": 0.4,
    "peer_agreement": 0.2,
    "recency": 0.1,
}

# Controller thresholds
SPAWN_UNCERTAINTY_THRESHOLD = 0.6
PRUNE_CONTRIBUTION_THRESHOLD = 0.1
MERGE_SIMILARITY_THRESHOLD = 0.85
ESCALATION_FAILURE_COUNT = 3
