"""Linter runner tool."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from plastic_agent_net.tools.repo import ToolResult

logger = logging.getLogger(__name__)


async def run_lint(
    workspace_path: str,
    command: list[str] | None = None,
    timeout: float = 60,
) -> ToolResult:
    """Run linters in the workspace."""
    if command is None:
        command = await _detect_lint_command(workspace_path)

    if not command:
        return ToolResult(tool="lint", success=True, output="No linter detected, skipping")

    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = stdout.decode(errors="replace") + "\n" + stderr.decode(errors="replace")
        return ToolResult(
            tool="lint",
            success=proc.returncode == 0,
            output=output.strip()[:5000],
            exit_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ToolResult(tool="lint", success=False, output=f"Lint timed out after {timeout}s", exit_code=-1)


async def _detect_lint_command(workspace_path: str) -> list[str]:
    """Auto-detect the linter."""
    ws = Path(workspace_path)

    # Python linters
    if any((ws / f).exists() for f in ("pyproject.toml", "setup.py", "setup.cfg")):
        # Try ruff first, then flake8
        for linter in [["ruff", "check", "."], ["flake8", "."]]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    linter[0], "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                await proc.communicate()
                if proc.returncode == 0:
                    return linter
            except FileNotFoundError:
                continue

    # JS/TS linters
    if (ws / "package.json").exists():
        return ["npm", "run", "lint"]

    return []
