/**
 * Port of prompts/schemas.py: output JSON schemas per agent type.
 */

export const PLANNER_SCHEMA = {
  type: "object",
  properties: {
    sub_tasks: {
      type: "array",
      items: {
        type: "object",
        properties: {
          description: { type: "string" },
          agent_type: { type: "string" },
          priority: { type: "integer" },
          estimated_complexity: { type: "string", enum: ["low", "medium", "high"] },
        },
        required: ["description", "agent_type"],
      },
    },
    strategy: { type: "string" },
    uncertainties: { type: "array", items: { type: "string" } },
    candidate_files: { type: "array", items: { type: "string" } },
    needs_branching: { type: "boolean" },
  },
  required: ["sub_tasks", "strategy"],
};

export const REPO_MAP_SCHEMA = {
  type: "object",
  properties: {
    relevant_files: {
      type: "array",
      items: {
        type: "object",
        properties: {
          path: { type: "string" },
          relevance: { type: "string" },
          symbols: { type: "array", items: { type: "string" } },
        },
        required: ["path", "relevance"],
      },
    },
    entry_points: { type: "array", items: { type: "string" } },
    dependencies: { type: "array", items: { type: "string" } },
  },
  required: ["relevant_files"],
};

export const CODER_SCHEMA = {
  type: "object",
  properties: {
    patches: {
      type: "array",
      items: {
        type: "object",
        properties: {
          file_path: { type: "string" },
          diff: { type: "string" },
          rationale: { type: "string" },
        },
        required: ["file_path", "diff"],
      },
    },
    risk_notes: { type: "array", items: { type: "string" } },
    confidence: { type: "number" },
  },
  required: ["patches"],
};

export const VERIFIER_SCHEMA = {
  type: "object",
  properties: {
    build_passed: { type: "boolean" },
    tests_passed: { type: "boolean" },
    test_summary: { type: "string" },
    lint_passed: { type: "boolean" },
    lint_issues: { type: "array", items: { type: "string" } },
    security_passed: { type: "boolean" },
    overall_score: { type: "number" },
    blocking_issues: { type: "array", items: { type: "string" } },
  },
  required: ["build_passed", "tests_passed", "overall_score"],
};

export const DEBUGGER_SCHEMA = {
  type: "object",
  properties: {
    root_cause: { type: "string" },
    confidence: { type: "number" },
    evidence: { type: "array", items: { type: "string" } },
    proposed_fix: {
      type: "object",
      properties: {
        file_path: { type: "string" },
        diff: { type: "string" },
        explanation: { type: "string" },
      },
    },
    alternative_causes: { type: "array", items: { type: "string" } },
  },
  required: ["root_cause", "confidence"],
};

export const TEST_WRITER_SCHEMA = {
  type: "object",
  properties: {
    test_files: {
      type: "array",
      items: {
        type: "object",
        properties: {
          file_path: { type: "string" },
          content: { type: "string" },
          test_type: { type: "string", enum: ["unit", "integration", "regression"] },
        },
        required: ["file_path", "content"],
      },
    },
    coverage_notes: { type: "string" },
  },
  required: ["test_files"],
};

export const REVIEWER_SCHEMA = {
  type: "object",
  properties: {
    verdict: { type: "string", enum: ["approve", "request_changes", "reject"] },
    issues: {
      type: "array",
      items: {
        type: "object",
        properties: {
          severity: { type: "string", enum: ["critical", "major", "minor", "nit"] },
          file_path: { type: "string" },
          description: { type: "string" },
          suggestion: { type: "string" },
        },
        required: ["severity", "description"],
      },
    },
    strengths: { type: "array", items: { type: "string" } },
    overall_assessment: { type: "string" },
  },
  required: ["verdict", "issues"],
};

export const SYNTHESIZER_SCHEMA = {
  type: "object",
  properties: {
    final_patches: {
      type: "array",
      items: {
        type: "object",
        properties: {
          file_path: { type: "string" },
          diff: { type: "string" },
        },
        required: ["file_path", "diff"],
      },
    },
    changes_summary: { type: "string" },
    review_responses: { type: "array", items: { type: "string" } },
  },
  required: ["final_patches", "changes_summary"],
};

export const TASK_ENCODER_SCHEMA = {
  type: "object",
  properties: {
    task_type: { type: "string", enum: ["bugfix", "feature", "refactor", "test", "docs"] },
    complexity: { type: "string", enum: ["low", "medium", "high"] },
    keywords: { type: "array", items: { type: "string" } },
    candidate_files: { type: "array", items: { type: "string" } },
  },
  required: ["task_type", "complexity"],
};

/** Map agent template name to its output schema. */
export const AGENT_SCHEMAS: Record<string, object> = {
  planner: PLANNER_SCHEMA,
  repo_mapper: REPO_MAP_SCHEMA,
  coder: CODER_SCHEMA,
  verifier_coordinator: VERIFIER_SCHEMA,
  debugger: DEBUGGER_SCHEMA,
  test_writer: TEST_WRITER_SCHEMA,
  skeptic_reviewer: REVIEWER_SCHEMA,
  security_reviewer: REVIEWER_SCHEMA,
  regression_reviewer: REVIEWER_SCHEMA,
  synthesizer: SYNTHESIZER_SCHEMA,
};
