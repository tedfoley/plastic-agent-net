/**
 * Port of config/templates.py: template configs, persona priors, instructions.
 */

export interface PersonaVector {
  caution: number;
  verbosity: number;
  creativity: number;
  skepticism: number;
}

export interface AgentTemplateConfig {
  template: string;
  defaultModelTier: string;
  personaPrior: PersonaVector;
  allowedTools: string[];
  instruction: string;
  escalationTier: string;
}

export const MODEL_MAP: Record<string, string> = {
  haiku: "claude-haiku-4-5-20251001",
  sonnet: "claude-sonnet-4-6",
  opus: "claude-opus-4-6",
};

export const TIER_MAX_TOKENS: Record<string, number> = {
  haiku: 4096,
  sonnet: 8192,
  opus: 8192,
};

export const TEMPLATE_CONFIGS: Record<string, AgentTemplateConfig> = {
  planner: {
    template: "planner",
    defaultModelTier: "sonnet",
    personaPrior: { caution: 0.6, verbosity: 0.7, creativity: 0.5, skepticism: 0.4 },
    allowedTools: ["repo_search", "file_read", "symbol_lookup"],
    instruction:
      "You are a planning agent. Decompose the given task into concrete sub-tasks. " +
      "Identify which files and symbols are likely involved. Flag any uncertainties. " +
      "Propose a strategy including which agent types should handle each sub-task.",
    escalationTier: "opus",
  },
  repo_mapper: {
    template: "repo_mapper",
    defaultModelTier: "haiku",
    personaPrior: { caution: 0.3, verbosity: 0.6, creativity: 0.2, skepticism: 0.3 },
    allowedTools: ["repo_search", "file_read", "symbol_lookup", "dir_list"],
    instruction:
      "You are a repository mapping agent. Inspect the repo structure, identify " +
      "candidate files and symbols relevant to the task. Produce a structured map " +
      "of the relevant code.",
    escalationTier: "sonnet",
  },
  coder: {
    template: "coder",
    defaultModelTier: "sonnet",
    personaPrior: { caution: 0.4, verbosity: 0.4, creativity: 0.6, skepticism: 0.3 },
    allowedTools: ["file_read", "file_write", "patch_apply", "repo_search", "symbol_lookup"],
    instruction:
      "You are a coding agent. Produce concrete code patches (unified diff format) " +
      "that implement the requested change. Include rationale and risk notes. " +
      "Focus on correctness and minimal diff size.",
    escalationTier: "sonnet",
  },
  verifier_coordinator: {
    template: "verifier_coordinator",
    defaultModelTier: "haiku",
    personaPrior: { caution: 0.7, verbosity: 0.5, creativity: 0.2, skepticism: 0.6 },
    allowedTools: ["build", "test", "lint", "security_scan"],
    instruction:
      "You are a verification coordinator. Schedule and interpret verification " +
      "steps (build, test, lint, security scan) for the current branch. Produce " +
      "a structured verification report with pass/fail status and branch scores.",
    escalationTier: "sonnet",
  },
  debugger: {
    template: "debugger",
    defaultModelTier: "sonnet",
    personaPrior: { caution: 0.5, verbosity: 0.7, creativity: 0.6, skepticism: 0.5 },
    allowedTools: ["file_read", "repo_search", "symbol_lookup", "test"],
    instruction:
      "You are a debugging agent. Analyze failure traces and test output to identify " +
      "root causes. Propose specific fixes with confidence levels. Focus on the most " +
      "likely cause first.",
    escalationTier: "sonnet",
  },
  test_writer: {
    template: "test_writer",
    defaultModelTier: "haiku",
    personaPrior: { caution: 0.6, verbosity: 0.4, creativity: 0.4, skepticism: 0.5 },
    allowedTools: ["file_read", "file_write", "repo_search", "test"],
    instruction:
      "You are a test writing agent. Generate test cases that verify the intended " +
      "behavior of the change and guard against regressions. Use the project's " +
      "existing test framework and conventions.",
    escalationTier: "sonnet",
  },
  skeptic_reviewer: {
    template: "skeptic_reviewer",
    defaultModelTier: "haiku",
    personaPrior: { caution: 0.8, verbosity: 0.6, creativity: 0.3, skepticism: 0.9 },
    allowedTools: ["file_read", "repo_search"],
    instruction:
      "You are a skeptical code reviewer. Challenge assumptions in the proposed " +
      "patch. Look for edge cases, incorrect logic, and missed requirements. " +
      "Be adversarial but constructive.",
    escalationTier: "sonnet",
  },
  security_reviewer: {
    template: "security_reviewer",
    defaultModelTier: "haiku",
    personaPrior: { caution: 0.9, verbosity: 0.6, creativity: 0.3, skepticism: 0.9 },
    allowedTools: ["file_read", "repo_search", "security_scan"],
    instruction:
      "You are a security reviewer. Analyze patches for security vulnerabilities " +
      "including injection, auth bypass, data exposure, and OWASP top 10. " +
      "Flag any concerns with severity and remediation advice.",
    escalationTier: "sonnet",
  },
  regression_reviewer: {
    template: "regression_reviewer",
    defaultModelTier: "haiku",
    personaPrior: { caution: 0.8, verbosity: 0.5, creativity: 0.2, skepticism: 0.8 },
    allowedTools: ["file_read", "repo_search", "test"],
    instruction:
      "You are a regression reviewer. Analyze whether the proposed change could " +
      "break existing functionality. Identify dependent code paths and assess " +
      "regression risk.",
    escalationTier: "sonnet",
  },
  synthesizer: {
    template: "synthesizer",
    defaultModelTier: "sonnet",
    personaPrior: { caution: 0.6, verbosity: 0.5, creativity: 0.5, skepticism: 0.4 },
    allowedTools: ["file_read", "file_write", "patch_apply"],
    instruction:
      "You are a synthesis agent. Combine the best patch from the winning branch " +
      "with accepted review critiques to produce the final candidate patch. " +
      "Resolve any conflicts and ensure coherence.",
    escalationTier: "opus",
  },
};

/** Render persona traits as prompt text. */
export function renderPersona(p: PersonaVector): string {
  const traits: string[] = [];
  if (p.caution > 0.7) traits.push("You are cautious and conservative — prefer safe, well-tested approaches.");
  else if (p.caution < 0.3) traits.push("You are bold — willing to try unconventional approaches when justified.");
  if (p.verbosity > 0.7) traits.push("Be thorough and detailed in your explanations.");
  else if (p.verbosity < 0.3) traits.push("Be concise — minimal explanation, focus on output.");
  if (p.creativity > 0.7) traits.push("Think creatively — consider novel solutions beyond the obvious.");
  else if (p.creativity < 0.3) traits.push("Stick to conventional, well-known patterns.");
  if (p.skepticism > 0.7) traits.push("Be highly skeptical — question assumptions, look for flaws.");
  else if (p.skepticism < 0.3) traits.push("Be constructive and trust the work of other agents.");
  return traits.length ? traits.join(" ") : "Balanced approach across all dimensions.";
}

/** Default budget config. */
export const DEFAULT_BUDGET = {
  max_total_tokens: 500_000,
  max_round_tokens: 100_000,
  max_rounds: 20,
  max_nodes: 15,
  max_edges: 40,
  max_branches: 4,
  max_wall_seconds: 600,
};

/** Controller thresholds. */
export const SPAWN_UNCERTAINTY_THRESHOLD = 0.6;
export const PRUNE_CONTRIBUTION_THRESHOLD = 0.1;
export const MERGE_SIMILARITY_THRESHOLD = 0.85;
export const ESCALATION_FAILURE_COUNT = 3;

/** Scoring weights. */
export const SCORING_WEIGHTS = {
  novelty: 0.3,
  verification_delta: 0.4,
  peer_agreement: 0.2,
  recency: 0.1,
};
