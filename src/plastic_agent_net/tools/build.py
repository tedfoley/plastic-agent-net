"""Build runner tool."""

from __future__ import annotations

import asyncio
import logging

from plastic_agent_net.tools.repo import ToolResult

logger = logging.getLogger(__name__)

# Common build commands to try
DEFAULT_BUILD_COMMANDS = [
    ["make"],
    ["python", "-m", "py_compile"],
    ["npm", "run", "build"],
    ["cargo", "build"],
]


async def run_build(workspace_path: str, command: list[str] | None = None, timeout: float = 120) -> ToolResult:
    """Run a build command in the workspace."""
    if command is None:
        command = await _detect_build_command(workspace_path)

    if not command:
        return ToolResult(tool="build", success=True, output="No build system detected, skipping")

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
            tool="build",
            success=proc.returncode == 0,
            output=output.strip()[:5000],
            exit_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ToolResult(tool="build", success=False, output=f"Build timed out after {timeout}s", exit_code=-1)


async def _detect_build_command(workspace_path: str) -> list[str]:
    """Auto-detect the build system."""
    from pathlib import Path
    ws = Path(workspace_path)

    if (ws / "Makefile").exists():
        return ["make"]
    if (ws / "package.json").exists():
        return ["npm", "run", "build"]
    if (ws / "Cargo.toml").exists():
        return ["cargo", "build"]
    if (ws / "setup.py").exists() or (ws / "pyproject.toml").exists():
        return ["python", "-m", "compileall", "-q", str(ws)]

    return []
