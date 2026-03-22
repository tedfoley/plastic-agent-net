"""Agent template definitions with persona priors and tool policies."""

from __future__ import annotations

from dataclasses import dataclass, field

from plastic_agent_net.core.models import AgentTemplate, ModelTier, PersonaVector


@dataclass
class AgentTemplateConfig:
    template: AgentTemplate
    default_model_tier: ModelTier
    persona_prior: PersonaVector
    allowed_tools: list[str]
    instruction: str
    escalation_tier: ModelTier = ModelTier.SONNET


TEMPLATE_CONFIGS: dict[AgentTemplate, AgentTemplateConfig] = {
    AgentTemplate.PLANNER: AgentTemplateConfig(
        template=AgentTemplate.PLANNER,
        default_model_tier=ModelTier.SONNET,
        persona_prior=PersonaVector(caution=0.6, verbosity=0.7, creativity=0.5, skepticism=0.4),
        allowed_tools=["repo_search", "file_read", "symbol_lookup"],
        instruction=(
            "You are a planning agent. Decompose the given task into concrete sub-tasks. "
            "Identify which files and symbols are likely involved. Flag any uncertainties. "
            "Propose a strategy including which agent types should handle each sub-task."
        ),
        escalation_tier=ModelTier.OPUS,
    ),
    AgentTemplate.REPO_MAPPER: AgentTemplateConfig(
        template=AgentTemplate.REPO_MAPPER,
        default_model_tier=ModelTier.HAIKU,
        persona_prior=PersonaVector(caution=0.3, verbosity=0.6, creativity=0.2, skepticism=0.3),
        allowed_tools=["repo_search", "file_read", "symbol_lookup", "dir_list"],
        instruction=(
            "You are a repository mapping agent. Inspect the repo structure, identify "
            "candidate files and symbols relevant to the task. Produce a structured map "
            "of the relevant code."
        ),
    ),
    AgentTemplate.CODER: AgentTemplateConfig(
        template=AgentTemplate.CODER,
        default_model_tier=ModelTier.SONNET,
        persona_prior=PersonaVector(caution=0.4, verbosity=0.4, creativity=0.6, skepticism=0.3),
        allowed_tools=["file_read", "file_write", "patch_apply", "repo_search", "symbol_lookup"],
        instruction=(
            "You are a coding agent. Produce concrete code patches (unified diff format) "
            "that implement the requested change. Include rationale and risk notes. "
            "Focus on correctness and minimal diff size."
        ),
    ),
    AgentTemplate.VERIFIER_COORDINATOR: AgentTemplateConfig(
        template=AgentTemplate.VERIFIER_COORDINATOR,
        default_model_tier=ModelTier.HAIKU,
        persona_prior=PersonaVector(caution=0.7, verbosity=0.5, creativity=0.2, skepticism=0.6),
        allowed_tools=["build", "test", "lint", "security_scan"],
        instruction=(
            "You are a verification coordinator. Schedule and interpret verification "
            "steps (build, test, lint, security scan) for the current branch. Produce "
            "a structured verification report with pass/fail status and branch scores."
        ),
    ),
    AgentTemplate.DEBUGGER: AgentTemplateConfig(
        template=AgentTemplate.DEBUGGER,
        default_model_tier=ModelTier.SONNET,
        persona_prior=PersonaVector(caution=0.5, verbosity=0.7, creativity=0.6, skepticism=0.5),
        allowed_tools=["file_read", "repo_search", "symbol_lookup", "test"],
        instruction=(
            "You are a debugging agent. Analyze failure traces and test output to identify "
            "root causes. Propose specific fixes with confidence levels. Focus on the most "
            "likely cause first."
        ),
    ),
    AgentTemplate.TEST_WRITER: AgentTemplateConfig(
        template=AgentTemplate.TEST_WRITER,
        default_model_tier=ModelTier.HAIKU,
        persona_prior=PersonaVector(caution=0.6, verbosity=0.4, creativity=0.4, skepticism=0.5),
        allowed_tools=["file_read", "file_write", "repo_search", "test"],
        instruction=(
            "You are a test writing agent. Generate test cases that verify the intended "
            "behavior of the change and guard against regressions. Use the project's "
            "existing test framework and conventions."
        ),
    ),
    AgentTemplate.SKEPTIC_REVIEWER: AgentTemplateConfig(
        template=AgentTemplate.SKEPTIC_REVIEWER,
        default_model_tier=ModelTier.HAIKU,
        persona_prior=PersonaVector(caution=0.8, verbosity=0.6, creativity=0.3, skepticism=0.9),
        allowed_tools=["file_read", "repo_search"],
        instruction=(
            "You are a skeptical code reviewer. Challenge assumptions in the proposed "
            "patch. Look for edge cases, incorrect logic, and missed requirements. "
            "Be adversarial but constructive."
        ),
    ),
    AgentTemplate.SECURITY_REVIEWER: AgentTemplateConfig(
        template=AgentTemplate.SECURITY_REVIEWER,
        default_model_tier=ModelTier.HAIKU,
        persona_prior=PersonaVector(caution=0.9, verbosity=0.6, creativity=0.3, skepticism=0.9),
        allowed_tools=["file_read", "repo_search", "security_scan"],
        instruction=(
            "You are a security reviewer. Analyze patches for security vulnerabilities "
            "including injection, auth bypass, data exposure, and OWASP top 10. "
            "Flag any concerns with severity and remediation advice."
        ),
    ),
    AgentTemplate.REGRESSION_REVIEWER: AgentTemplateConfig(
        template=AgentTemplate.REGRESSION_REVIEWER,
        default_model_tier=ModelTier.HAIKU,
        persona_prior=PersonaVector(caution=0.8, verbosity=0.5, creativity=0.2, skepticism=0.8),
        allowed_tools=["file_read", "repo_search", "test"],
        instruction=(
            "You are a regression reviewer. Analyze whether the proposed change could "
            "break existing functionality. Identify dependent code paths and assess "
            "regression risk."
        ),
    ),
    AgentTemplate.SYNTHESIZER: AgentTemplateConfig(
        template=AgentTemplate.SYNTHESIZER,
        default_model_tier=ModelTier.SONNET,
        persona_prior=PersonaVector(caution=0.6, verbosity=0.5, creativity=0.5, skepticism=0.4),
        allowed_tools=["file_read", "file_write", "patch_apply"],
        instruction=(
            "You are a synthesis agent. Combine the best patch from the winning branch "
            "with accepted review critiques to produce the final candidate patch. "
            "Resolve any conflicts and ensure coherence."
        ),
        escalation_tier=ModelTier.OPUS,
    ),
}
