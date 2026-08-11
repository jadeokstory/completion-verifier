import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

from ..redaction import redact
from ..timeutil import isoformat, utc_now
from ..verdict import Verdict


_OUTPUT_LIMIT = 4_000


def _as_bytes(value: str | bytes | None) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return value.encode("utf-8")


def _as_text(value: bytes) -> str:
    return value.decode("utf-8", errors="replace")


def _excerpt(value: str) -> tuple[str, bool]:
    if len(value) <= _OUTPUT_LIMIT:
        return value, False
    return value[:_OUTPUT_LIMIT], True


def verify_command(check: dict[str, Any], root: Path) -> dict[str, Any]:
    command = check["command"]
    started = utc_now()
    exit_code: int | None = None
    timed_out = False
    stdout_bytes = b""
    stderr_bytes = b""

    try:
        completed = subprocess.run(
            command,
            cwd=root,
            capture_output=True,
            check=False,
            timeout=check["timeout_seconds"],
        )
        exit_code = completed.returncode
        stdout_bytes = completed.stdout
        stderr_bytes = completed.stderr
        if exit_code == 0:
            verdict = Verdict.PASS
            reason = "command exited with code 0"
        else:
            verdict = Verdict.FAIL
            reason = f"command exited with code {exit_code}"
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout_bytes = _as_bytes(error.stdout)
        stderr_bytes = _as_bytes(error.stderr)
        verdict = Verdict.FAIL
        reason = f"command exceeded timeout of {check['timeout_seconds']} seconds"
    except FileNotFoundError:
        verdict = Verdict.BLOCKED
        reason = f"executable not found: {command[0]}"
    except PermissionError:
        verdict = Verdict.BLOCKED
        reason = f"permission denied starting executable: {command[0]}"
    except OSError as error:
        verdict = Verdict.BLOCKED
        reason = f"could not start command: {error.strerror or error}"

    finished = utc_now()
    output_sha256 = hashlib.sha256(stdout_bytes + b"\0" + stderr_bytes).hexdigest()
    command_sha256 = hashlib.sha256(
        json.dumps(command, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    stdout = _as_text(stdout_bytes)
    stderr = _as_text(stderr_bytes)
    redacted_arguments = [redact(argument) for argument in command]
    reason_redacted = redact(reason)
    stdout_redacted = redact(stdout)
    stderr_redacted = redact(stderr)
    stdout_excerpt, stdout_truncated = _excerpt(stdout_redacted.text)
    stderr_excerpt, stderr_truncated = _excerpt(stderr_redacted.text)

    return {
        "id": check["id"],
        "type": "command",
        "verdict": verdict.value,
        "reason": reason_redacted.text,
        "evidence": {
            "command": [argument.text for argument in redacted_arguments],
            "command_sha256": command_sha256,
            "started_at": isoformat(started),
            "finished_at": isoformat(finished),
            "exit_code": exit_code,
            "timeout_seconds": check["timeout_seconds"],
            "timed_out": timed_out,
            "output_sha256": output_sha256,
            "stdout": stdout_excerpt,
            "stderr": stderr_excerpt,
            "stdout_truncated": stdout_truncated,
            "stderr_truncated": stderr_truncated,
            "redaction_applied": any(
                argument.applied for argument in redacted_arguments
            )
            or stdout_redacted.applied
            or stderr_redacted.applied
            or reason_redacted.applied,
        },
    }
