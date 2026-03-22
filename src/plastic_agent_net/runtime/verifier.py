"""Verifier: orchestrate tool execution per branch."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from plastic_agent_net.core.models import Artifact, ArtifactType
from plastic_agent_net.memory.artifact_store import ArtifactStore
from plastic_agent_net.tools.build import run_build
from plastic_agent_net.tools.lint import run_lint
from plastic_agent_net.tools.patch import apply_patch
from plastic_agent_net.tools.repo import ToolResult
from plastic_agent_net.tools.security import run_security_scan
from plastic_agent_net.tools.tests import run_tests
from plastic_agent_net.tools.workspace import WorkspaceManager

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    branch_id: str
    build: ToolResult | None = None
    tests: ToolResult | None = None
    lint: ToolResult | None = None
    security: ToolResult | None = None
    patch_applied: bool = False
    overall_score: float = 0.0
    blocking_issues: list[str] = field(default_factory=list)


class Verifier:
    """Orchestrates verification of a branch's patches."""

    def __init__(
        self,
        workspace_manager: WorkspaceManager,
        artifact_store: ArtifactStore,
    ) -> None:
        self._ws_manager = workspace_manager
        self._artifact_store = artifact_store

    async def evaluate_branch(self, branch_id: str, current_round: int) -> VerificationResult:
        """Apply patches → build → test → lint → security scan → score."""
        result = VerificationResult(branch_id=branch_id)

        ws = self._ws_manager.get(branch_id)
        if ws is None:
            ws = await self._ws_manager.create(branch_id)

        workspace_path = str(ws.path)

        # Apply all patches for this branch
        patches = self._artifact_store.list_by_branch(branch_id)
        patch_artifacts = [a for a in patches if a.artifact_type == ArtifactType.PATCH]

        for pa in patch_artifacts:
            for p in pa.content.get("patches", []):
                patch_result = await apply_patch(
                    workspace_path,
                    p.get("diff", ""),
                    p.get("file_path"),
                )
                if not patch_result.success:
                    result.blocking_issues.append(f"Patch failed: {patch_result.output[:200]}")
                else:
                    result.patch_applied = True

        # Build
        result.build = await run_build(workspace_path)
        if not result.build.success:
            result.blocking_issues.append(f"Build failed: {result.build.output[:200]}")

        # Tests
        result.tests = await run_tests(workspace_path)
        if not result.tests.success:
            result.blocking_issues.append(f"Tests failed: {result.tests.output[:200]}")

        # Lint
        result.lint = await run_lint(workspace_path)

        # Security scan (non-blocking)
        result.security = await run_security_scan(workspace_path)

        # Compute score
        result.overall_score = self._compute_score(result)

        # Store as artifact
        artifact = Artifact(
            artifact_type=ArtifactType.VERIFICATION,
            producer_node="verifier",
            branch_id=branch_id,
            round_produced=current_round,
            content={
                "build_passed": result.build.success if result.build else True,
                "tests_passed": result.tests.success if result.tests else True,
                "lint_passed": result.lint.success if result.lint else True,
                "security_passed": result.security.success if result.security else True,
                "overall_score": result.overall_score,
                "blocking_issues": result.blocking_issues,
            },
            summary=f"score={result.overall_score:.2f}, issues={len(result.blocking_issues)}",
        )
        self._artifact_store.put(artifact)

        return result

    def _compute_score(self, result: VerificationResult) -> float:
        score = 0.0
        if result.patch_applied:
            score += 0.1
        if result.build and result.build.success:
            score += 0.3
        if result.tests and result.tests.success:
            score += 0.4
        if result.lint and result.lint.success:
            score += 0.1
        if result.security and result.security.success:
            score += 0.1
        return score
