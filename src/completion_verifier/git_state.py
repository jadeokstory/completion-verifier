import subprocess
from pathlib import Path
from typing import Any


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def observe_git_state(root: Path) -> dict[str, Any]:
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}") if commit else None
    status = _git(root, "status", "--porcelain=v1") if commit else None
    return {
        "commit": commit,
        "tree": tree,
        "dirty": bool(status) if status is not None else None,
    }
