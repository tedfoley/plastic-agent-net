"""Patch apply/revert tool."""

from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

from plastic_agent_net.tools.repo import ToolResult


async def apply_patch(workspace_path: str, diff: str, file_path: str | None = None) -> ToolResult:
    """Apply a unified diff to a workspace."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(diff)
        patch_file = f.name

    try:
        # Try git apply first
        proc = await asyncio.create_subprocess_exec(
            "git", "apply", "--allow-empty", patch_file,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return ToolResult(tool="patch_apply", success=True, output="Patch applied successfully")

        # Fall back to patch command
        proc = await asyncio.create_subprocess_exec(
            "patch", "-p1", "-i", patch_file,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()

        if proc.returncode == 0:
            return ToolResult(tool="patch_apply", success=True, output=stdout.decode(errors="replace"))

        # Last resort: direct file write if we have a file_path
        if file_path:
            return await _direct_write(workspace_path, diff, file_path)

        return ToolResult(
            tool="patch_apply",
            success=False,
            output=f"Patch failed: {stderr.decode(errors='replace')}",
            exit_code=proc.returncode,
        )
    finally:
        Path(patch_file).unlink(missing_ok=True)


async def _direct_write(workspace_path: str, content: str, file_path: str) -> ToolResult:
    """Direct file write as last-resort patch application."""
    try:
        full_path = Path(workspace_path) / file_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content)
        return ToolResult(tool="patch_apply", success=True, output=f"Direct write to {file_path}")
    except OSError as e:
        return ToolResult(tool="patch_apply", success=False, output=str(e), exit_code=1)


async def revert_patch(workspace_path: str, diff: str) -> ToolResult:
    """Revert a previously applied patch."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as f:
        f.write(diff)
        patch_file = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            "git", "apply", "--reverse", patch_file,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        success = proc.returncode == 0
        return ToolResult(
            tool="patch_revert",
            success=success,
            output=stdout.decode(errors="replace") if success else stderr.decode(errors="replace"),
            exit_code=proc.returncode,
        )
    finally:
        Path(patch_file).unlink(missing_ok=True)
