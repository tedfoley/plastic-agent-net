"""Test runner tool."""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from plastic_agent_net.tools.repo import ToolResult

logger = logging.getLogger(__name__)


async def run_tests(
    workspace_path: str,
    command: list[str] | None = None,
    timeout: float = 180,
) -> ToolResult:
    """Run tests in the workspace and parse results."""
    if command is None:
        command = await _detect_test_command(workspace_path)

    if not command:
        return ToolResult(tool="test", success=True, output="No test framework detected, skipping")

    try:
        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)

        output = stdout.decode(errors="replace") + "\n" + stderr.decode(errors="replace")

        # Try to parse pytest JSON report
        report_path = Path(workspace_path) / ".pan_test_report.json"
        parsed_summary = ""
        if report_path.exists():
            try:
                report = json.loads(report_path.read_text())
                summary = report.get("summary", {})
                parsed_summary = (
                    f"\nParsed: {summary.get('passed', 0)} passed, "
                    f"{summary.get('failed', 0)} failed, "
                    f"{summary.get('error', 0)} errors"
                )
                report_path.unlink()
            except (json.JSONDecodeError, OSError):
                pass

        return ToolResult(
            tool="test",
            success=proc.returncode == 0,
            output=(output.strip() + parsed_summary)[:5000],
            exit_code=proc.returncode or 0,
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ToolResult(tool="test", success=False, output=f"Tests timed out after {timeout}s", exit_code=-1)


async def _detect_test_command(workspace_path: str) -> list[str]:
    """Auto-detect the test framework."""
    ws = Path(workspace_path)

    if (ws / "pytest.ini").exists() or (ws / "pyproject.toml").exists() or (ws / "setup.cfg").exists():
        return [
            "python", "-m", "pytest", "-x", "--tb=short",
            f"--json-report-file={ws / '.pan_test_report.json'}",
        ]
    if (ws / "package.json").exists():
        return ["npm", "test"]
    if (ws / "Cargo.toml").exists():
        return ["cargo", "test"]

    # Check for any test files
    test_files = list(ws.glob("**/test_*.py")) + list(ws.glob("**/*_test.py"))
    if test_files:
        return ["python", "-m", "pytest", "-x", "--tb=short"]

    return []
