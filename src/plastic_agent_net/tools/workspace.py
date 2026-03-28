"""Isolated workspace manager: git worktrees or temp dirs."""

from __future__ import annotations

import asyncio
import logging
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Workspace:
    workspace_id: str
    path: Path
    branch_id: str
    is_worktree: bool = False
    active: bool = True


class WorkspaceManager:
    """Creates and manages isolated workspaces for branches."""

    def __init__(self, base_repo: str | None = None) -> None:
        self._base_repo = Path(base_repo) if base_repo else None
        self._workspaces: dict[str, Workspace] = {}
        self._temp_dir = Path(tempfile.mkdtemp(prefix="pan_workspaces_"))

    async def create(self, branch_id: str) -> Workspace:
        """Create an isolated workspace for a branch."""
        if self._base_repo and (self._base_repo / ".git").exists():
            return await self._create_worktree(branch_id)
        return await self._create_tempdir(branch_id)

    async def _create_worktree(self, branch_id: str) -> Workspace:
        import uuid
        suffix = uuid.uuid4().hex[:8]
        worktree_path = self._temp_dir / f"wt_{branch_id}_{suffix}"
        git_branch = f"pan/{branch_id}_{suffix}"
        proc = await asyncio.create_subprocess_exec(
            "git", "worktree", "add", "-b", git_branch,
            str(worktree_path), "HEAD",
            cwd=str(self._base_repo),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning("Worktree creation failed: %s, falling back to tempdir", stderr.decode())
            return await self._create_tempdir(branch_id)

        ws = Workspace(
            workspace_id=branch_id,
            path=worktree_path,
            branch_id=branch_id,
            is_worktree=True,
        )
        self._workspaces[branch_id] = ws
        return ws

    async def _create_tempdir(self, branch_id: str) -> Workspace:
        ws_path = self._temp_dir / f"tmp_{branch_id}"
        ws_path.mkdir(parents=True, exist_ok=True)
        if self._base_repo:
            proc = await asyncio.create_subprocess_exec(
                "cp", "-r",
                *[str(p) for p in self._base_repo.iterdir() if p.name != ".git"],
                str(ws_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

        ws = Workspace(
            workspace_id=branch_id,
            path=ws_path,
            branch_id=branch_id,
            is_worktree=False,
        )
        self._workspaces[branch_id] = ws
        return ws

    def get(self, branch_id: str) -> Workspace | None:
        return self._workspaces.get(branch_id)

    async def destroy(self, branch_id: str) -> None:
        ws = self._workspaces.pop(branch_id, None)
        if ws is None:
            return
        ws.active = False
        if ws.is_worktree and self._base_repo:
            proc = await asyncio.create_subprocess_exec(
                "git", "worktree", "remove", "--force", str(ws.path),
                cwd=str(self._base_repo),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()
        elif ws.path.exists():
            shutil.rmtree(ws.path, ignore_errors=True)

    async def cleanup_all(self) -> None:
        for branch_id in list(self._workspaces):
            await self.destroy(branch_id)
        if self._temp_dir.exists():
            shutil.rmtree(self._temp_dir, ignore_errors=True)
