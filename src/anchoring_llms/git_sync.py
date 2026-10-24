"""Committing and pushing results to GitHub from inside a run (e.g. on Colab)."""

from __future__ import annotations

import subprocess
import time
from pathlib import Path


class GitSync:
    def __init__(self, repo_dir: str | Path, paths: list[str | Path], enabled: bool = False,
                 min_interval: float = 600):
        self.repo_dir = Path(repo_dir)
        self.paths = [str(p) for p in paths]
        self.enabled = enabled
        self.min_interval = min_interval
        self._last = time.time()

    def _git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=self.repo_dir, capture_output=True, text=True)

    def maybe_sync(self, message: str, force: bool = False) -> bool:
        if not self.enabled:
            return False
        if not force and time.time() - self._last < self.min_interval:
            return False
        self._last = time.time()
        self._git("add", "--", *self.paths)
        if self._git("diff", "--cached", "--quiet").returncode == 0:
            return False
        commit = self._git("commit", "-m", message)
        if commit.returncode != 0:
            print("[sync] commit failed:", commit.stderr.strip()[:300])
            return False
        for attempt in range(4):
            self._git("pull", "--rebase", "--autostash")
            push = self._git("push")
            if push.returncode == 0:
                print(f"[sync] pushed: {message}")
                return True
            print(f"[sync] push failed (attempt {attempt + 1}):", push.stderr.strip()[:300])
            time.sleep(2 ** (attempt + 1))
        return False
