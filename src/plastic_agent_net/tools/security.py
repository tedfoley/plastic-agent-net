"""Security scanner adapter."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from plastic_agent_net.tools.repo import ToolResult

logger = logging.getLogger(__name__)


async def run_security_scan(
    workspace_path: str,
    command: list[str] | None = None,
    timeout: float = 120,
) -> ToolResult:
    """Run a security scan on the workspace."""
    if command is None:
        command = await _detect_security_scanner(workspace_path)

    if not command:
        return ToolResult(tool="security", success=True, output="No security scanner detected, skipping")

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
            tool="security",
            success=proc.returncode == 0,
            output=output.strip()[:5000],
            exit_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ToolResult(tool="security", success=False, output=f"Security scan timed out after {timeout}s", exit_code=-1)


async def _detect_security_scanner(workspace_path: str) -> list[str]:
    """Auto-detect available security scanner."""
    ws = Path(workspace_path)

    # Python: try bandit
    if any((ws / f).exists() for f in ("pyproject.toml", "setup.py")):
        try:
            proc = await asyncio.create_subprocess_exec(
                "bandit", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
            if proc.returncode == 0:
                return ["bandit", "-r", ".", "-f", "json", "-q"]
        except FileNotFoundError:
            pass

    return []
