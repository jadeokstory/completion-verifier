import hashlib
import subprocess
from pathlib import Path
from typing import Any


def _git_bytes(root: Path, *args: str) -> bytes | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _git(root: Path, *args: str) -> str | None:
    result = _git_bytes(root, *args)
    if result is None:
        return None
    return result.decode("utf-8", errors="replace").strip()


def observe_git_state(root: Path) -> dict[str, Any]:
    commit = _git(root, "rev-parse", "HEAD")
    tree = _git(root, "rev-parse", "HEAD^{tree}") if commit else None
    status = (
        _git_bytes(
            root,
            "status",
            "--porcelain=v1",
            "-z",
            "--untracked-files=all",
        )
        if commit
        else None
    )
    return {
        "commit": commit,
        "tree": tree,
        "dirty": bool(status) if status is not None else None,
        "status_sha256": hashlib.sha256(status).hexdigest()
        if status is not None
        else None,
    }
