import json
import os
import shlex
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_RECEIPT_DIR = ".completion-verifier"
JSON_RECEIPT_NAME = "receipt.json"
MARKDOWN_RECEIPT_NAME = "receipt.md"


def render_markdown(receipt: dict[str, Any]) -> str:
    lines = [
        f"# {receipt['gate']}: {receipt['verdict']}",
        "",
        f"- Started: `{receipt['started_at']}`",
        f"- Finished: `{receipt['finished_at']}`",
        f"- Working directory: `{receipt['working_directory']}`",
        f"- Git commit: `{receipt['git']['after']['commit'] or 'unavailable'}`",
        f"- Redaction applied: `{'yes' if receipt['redaction_applied'] else 'no'}`",
        "",
        "| Check | Type | Verdict | Reason |",
        "| --- | --- | --- | --- |",
    ]
    for check in receipt["checks"]:
        reason = str(check["reason"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{check['id']}` | `{check['type']}` | "
            f"**{check['verdict']}** | {reason} |"
        )

    lines.extend(["", "## Evidence", ""])
    for check in receipt["checks"]:
        evidence = check["evidence"]
        lines.append(f"### {check['id']}")
        lines.append("")
        if check["type"] == "command":
            lines.extend(
                [
                    f"- Command: `{shlex.join(evidence['command'])}`",
                    f"- Command SHA-256: `{evidence['command_sha256']}`",
                    f"- Exit code: `{evidence['exit_code']}`",
                    f"- Timed out: `{str(evidence['timed_out']).lower()}`",
                    f"- Output SHA-256: `{evidence['output_sha256']}`",
                ]
            )
        else:
            lines.extend(
                [
                    f"- Path: `{evidence['path']}`",
                    f"- Size: `{evidence.get('size_bytes', 'unavailable')}` bytes",
                    f"- Modified: `{evidence.get('modified_at', 'unavailable')}`",
                    f"- SHA-256: `{evidence.get('sha256', 'unavailable')}`",
                    f"- Freshness: `{evidence['freshness']}`",
                ]
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", text=True
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file_handle:
            file_handle.write(content)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        os.replace(temporary_path, path)
        path.chmod(0o600)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def write_receipts(receipt: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    json_path = output_dir / JSON_RECEIPT_NAME
    markdown_path = output_dir / MARKDOWN_RECEIPT_NAME
    _atomic_write(
        json_path,
        json.dumps(receipt, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
    )
    _atomic_write(markdown_path, render_markdown(receipt))
    return json_path, markdown_path
