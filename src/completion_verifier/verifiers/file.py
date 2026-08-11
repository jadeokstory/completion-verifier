import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..timeutil import isoformat, utc_now
from ..verdict import Verdict


def _result(
    check: dict[str, Any], verdict: Verdict, reason: str, evidence: dict[str, Any]
) -> dict[str, Any]:
    return {
        "id": check["id"],
        "type": "file",
        "verdict": verdict.value,
        "reason": reason,
        "evidence": evidence,
    }


def verify_file(
    check: dict[str, Any], root: Path, run_started_ns: int
) -> dict[str, Any]:
    observed_at = isoformat(utc_now())
    relative_path = check["path"]
    candidate = root / relative_path
    evidence: dict[str, Any] = {
        "path": relative_path,
        "observed_at": observed_at,
        "freshness": check["freshness"],
    }

    try:
        root_resolved = root.resolve(strict=True)
        target_resolved = candidate.resolve(strict=False)
        if not target_resolved.is_relative_to(root_resolved):
            return _result(
                check,
                Verdict.BLOCKED,
                "resolved path escapes the contract directory",
                evidence,
            )

        if not candidate.exists():
            return _result(check, Verdict.FAIL, "file does not exist", evidence)
        if not candidate.is_file():
            return _result(check, Verdict.FAIL, "path is not a regular file", evidence)

        digest = hashlib.sha256()
        with candidate.open("rb") as file_handle:
            before = os.fstat(file_handle.fileno())
            while chunk := file_handle.read(1024 * 1024):
                digest.update(chunk)
            after = os.fstat(file_handle.fileno())
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            return _result(
                check,
                Verdict.BLOCKED,
                "file changed while it was being observed",
                evidence,
            )
    except PermissionError:
        return _result(check, Verdict.BLOCKED, "permission denied reading file", evidence)
    except OSError as error:
        return _result(
            check,
            Verdict.BLOCKED,
            f"could not observe file: {error.strerror or error}",
            evidence,
        )

    modified_at = datetime.fromtimestamp(before.st_mtime, tz=timezone.utc)
    evidence.update(
        {
            "size_bytes": before.st_size,
            "modified_at": isoformat(modified_at),
            "sha256": digest.hexdigest(),
            "min_bytes": check.get("min_bytes", 0),
        }
    )

    min_bytes = check.get("min_bytes", 0)
    if before.st_size < min_bytes:
        return _result(
            check,
            Verdict.FAIL,
            f"file is {before.st_size} bytes; minimum is {min_bytes}",
            evidence,
        )
    if check["freshness"] == "run" and before.st_mtime_ns < run_started_ns:
        return _result(
            check,
            Verdict.UNPROVEN,
            "file predates this verification run",
            evidence,
        )
    return _result(check, Verdict.PASS, "file satisfies the contract", evidence)
