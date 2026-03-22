"""Output JSON schemas per agent type."""

from plastic_agent_net.core.models import AgentTemplate

PLANNER_SCHEMA = {
    "type": "object",
    "properties": {
        "sub_tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "agent_type": {"type": "string"},
                    "priority": {"type": "integer"},
                    "estimated_complexity": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "required": ["description", "agent_type"],
            },
        },
        "strategy": {"type": "string"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
        "candidate_files": {"type": "array", "items": {"type": "string"}},
        "needs_branching": {"type": "boolean"},
    },
    "required": ["sub_tasks", "strategy"],
}

REPO_MAP_SCHEMA = {
    "type": "object",
    "properties": {
        "relevant_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "relevance": {"type": "string"},
                    "symbols": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["path", "relevance"],
            },
        },
        "entry_points": {"type": "array", "items": {"type": "string"}},
        "dependencies": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["relevant_files"],
}

CODER_SCHEMA = {
    "type": "object",
    "properties": {
        "patches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "diff": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["file_path", "diff"],
            },
        },
        "risk_notes": {"type": "array", "items": {"type": "string"}},
        "confidence": {"type": "number"},
    },
    "required": ["patches"],
}

VERIFIER_SCHEMA = {
    "type": "object",
    "properties": {
        "build_passed": {"type": "boolean"},
        "tests_passed": {"type": "boolean"},
        "test_summary": {"type": "string"},
        "lint_passed": {"type": "boolean"},
        "lint_issues": {"type": "array", "items": {"type": "string"}},
        "security_passed": {"type": "boolean"},
        "overall_score": {"type": "number"},
        "blocking_issues": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["build_passed", "tests_passed", "overall_score"],
}

DEBUGGER_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause": {"type": "string"},
        "confidence": {"type": "number"},
        "evidence": {"type": "array", "items": {"type": "string"}},
        "proposed_fix": {
            "type": "object",
            "properties": {
                "file_path": {"type": "string"},
                "diff": {"type": "string"},
                "explanation": {"type": "string"},
            },
        },
        "alternative_causes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["root_cause", "confidence"],
}

TEST_WRITER_SCHEMA = {
    "type": "object",
    "properties": {
        "test_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                    "test_type": {"type": "string", "enum": ["unit", "integration", "regression"]},
                },
                "required": ["file_path", "content"],
            },
        },
        "coverage_notes": {"type": "string"},
    },
    "required": ["test_files"],
}

REVIEWER_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["approve", "request_changes", "reject"]},
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["critical", "major", "minor", "nit"]},
                    "file_path": {"type": "string"},
                    "description": {"type": "string"},
                    "suggestion": {"type": "string"},
                },
                "required": ["severity", "description"],
            },
        },
        "strengths": {"type": "array", "items": {"type": "string"}},
        "overall_assessment": {"type": "string"},
    },
    "required": ["verdict", "issues"],
}

SYNTHESIZER_SCHEMA = {
    "type": "object",
    "properties": {
        "final_patches": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "diff": {"type": "string"},
                },
                "required": ["file_path", "diff"],
            },
        },
        "changes_summary": {"type": "string"},
        "review_responses": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["final_patches", "changes_summary"],
}

TASK_ENCODER_SCHEMA = {
    "type": "object",
    "properties": {
        "task_type": {"type": "string", "enum": ["bugfix", "feature", "refactor", "test", "docs"]},
        "complexity": {"type": "string", "enum": ["low", "medium", "high"]},
        "keywords": {"type": "array", "items": {"type": "string"}},
        "candidate_files": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["task_type", "complexity"],
}

AGENT_SCHEMAS: dict[AgentTemplate, dict] = {
    AgentTemplate.PLANNER: PLANNER_SCHEMA,
    AgentTemplate.REPO_MAPPER: REPO_MAP_SCHEMA,
    AgentTemplate.CODER: CODER_SCHEMA,
    AgentTemplate.VERIFIER_COORDINATOR: VERIFIER_SCHEMA,
    AgentTemplate.DEBUGGER: DEBUGGER_SCHEMA,
    AgentTemplate.TEST_WRITER: TEST_WRITER_SCHEMA,
    AgentTemplate.SKEPTIC_REVIEWER: REVIEWER_SCHEMA,
    AgentTemplate.SECURITY_REVIEWER: REVIEWER_SCHEMA,
    AgentTemplate.REGRESSION_REVIEWER: REVIEWER_SCHEMA,
    AgentTemplate.SYNTHESIZER: SYNTHESIZER_SCHEMA,
}
