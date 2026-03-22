"""Repo search, file read, symbol lookup tools."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    tool: str
    success: bool
    output: str
    exit_code: int = 0


async def file_read(workspace_path: str, file_path: str) -> ToolResult:
    """Read a file from the workspace."""
    full = Path(workspace_path) / file_path
    try:
        content = full.read_text()
        return ToolResult(tool="file_read", success=True, output=content)
    except (FileNotFoundError, PermissionError) as e:
        return ToolResult(tool="file_read", success=False, output=str(e), exit_code=1)


async def dir_list(workspace_path: str, dir_path: str = ".") -> ToolResult:
    """List directory contents."""
    full = Path(workspace_path) / dir_path
    if not full.is_dir():
        return ToolResult(tool="dir_list", success=False, output=f"Not a directory: {dir_path}", exit_code=1)
    entries = sorted(str(p.relative_to(full)) for p in full.iterdir())
    return ToolResult(tool="dir_list", success=True, output="\n".join(entries))


async def repo_search(workspace_path: str, pattern: str, file_glob: str = "**/*") -> ToolResult:
    """Search for a pattern in the workspace using grep/ripgrep."""
    # Try ripgrep first, fall back to grep
    for cmd in [["rg", "--no-heading", "-n", pattern, "."], ["grep", "-rn", pattern, "."]]:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode in (0, 1):  # 1 = no matches (normal)
            return ToolResult(
                tool="repo_search",
                success=True,
                output=stdout.decode(errors="replace")[:10000],
                exit_code=proc.returncode,
            )

    return ToolResult(tool="repo_search", success=False, output="No search tools available", exit_code=1)


async def symbol_lookup(workspace_path: str, symbol: str) -> ToolResult:
    """Look up a symbol (function/class/variable) in the workspace."""
    patterns = [
        f"(def|class|function|const|let|var)\\s+{symbol}",
        f"{symbol}\\s*=",
        f"{symbol}\\s*\\(",
    ]
    combined = "|".join(patterns)
    return await repo_search(workspace_path, combined)


async def repo_summary(repo_path: str, max_depth: int = 3) -> str:
    """Generate a brief summary of the repo structure."""
    path = Path(repo_path)
    if not path.is_dir():
        return f"Not a directory: {repo_path}"

    lines = []
    for item in sorted(path.rglob("*")):
        rel = item.relative_to(path)
        if len(rel.parts) > max_depth:
            continue
        if any(p.startswith(".") for p in rel.parts):
            continue
        if any(p in ("node_modules", "__pycache__", ".git", "venv", ".venv") for p in rel.parts):
            continue
        prefix = "  " * (len(rel.parts) - 1)
        name = rel.name + ("/" if item.is_dir() else "")
        lines.append(f"{prefix}{name}")
        if len(lines) > 200:
            lines.append("  ... (truncated)")
            break

    return "\n".join(lines) if lines else "(empty repo)"
