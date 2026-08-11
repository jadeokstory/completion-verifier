#!/usr/bin/env python3
"""Install and run ProofGate's Codex hooks without a separate package install."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Sequence


RUNTIME_DIR_ENV = "PROOFGATE_RUNTIME_DIR"
HOOKS_FILE_ENV = "PROOFGATE_HOOKS_FILE"
_RUNTIME_PACKAGE_FILES = (
    "__init__.py",
    "claim-evaluation.schema.json",
    "codex_integration.py",
    "redaction.py",
    "verdict.py",
)


def _source_root() -> Path:
    script_parent = Path(__file__).resolve().parent
    if (script_parent / "completion_verifier").is_dir():
        return script_parent
    return script_parent.parent


def _package_root(root: Path) -> Path:
    source_package = root / "src" / "completion_verifier"
    if source_package.is_dir():
        return source_package
    runtime_package = root / "completion_verifier"
    if runtime_package.is_dir():
        return runtime_package
    raise RuntimeError(f"ProofGate runtime package is missing under {root}")


def _load_engine() -> None:
    root = _source_root()
    package_root = _package_root(root)
    sys.path.insert(0, str(package_root.parent))


_load_engine()

from completion_verifier.codex_integration import (  # noqa: E402
    ALL_PROJECTS_ENV,
    CodexIntegrationError,
    default_hooks_file,
    handle_codex_hook,
    hooks_installed,
    install_hooks,
    uninstall_hooks,
)


def _default_runtime_dir() -> Path:
    configured = os.environ.get(RUNTIME_DIR_ENV)
    if configured:
        return Path(configured).expanduser()
    xdg_data = os.environ.get("XDG_DATA_HOME")
    if xdg_data:
        return Path(xdg_data).expanduser() / "proofgate" / "runtime"
    return Path.home() / ".local" / "share" / "proofgate" / "runtime"


def _hooks_path(raw_path: Path | None) -> Path:
    if raw_path is not None:
        return raw_path.expanduser()
    configured = os.environ.get(HOOKS_FILE_ENV)
    if configured:
        return Path(configured).expanduser()
    return default_hooks_file()


def _runtime_path(raw_path: Path | None) -> Path:
    return (raw_path or _default_runtime_dir()).expanduser().resolve()


def _ensure_private_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _atomic_copy(source: Path, destination: Path, mode: int) -> None:
    data = source.read_bytes()
    _ensure_private_directory(destination.parent)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}."
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "wb") as file_handle:
            file_handle.write(data)
            file_handle.flush()
            os.fsync(file_handle.fileno())
        temporary_path.chmod(mode)
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _atomic_write_json(destination: Path, value: dict[str, str]) -> None:
    _ensure_private_directory(destination.parent)
    file_descriptor, temporary_name = tempfile.mkstemp(
        dir=destination.parent, prefix=f".{destination.name}.", text=True
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as file_handle:
            json.dump(value, file_handle, ensure_ascii=False, indent=2)
            file_handle.write("\n")
            file_handle.flush()
            os.fsync(file_handle.fileno())
        temporary_path.chmod(0o600)
        os.replace(temporary_path, destination)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


def _copy_runtime(runtime_dir: Path) -> Path:
    source_root = _source_root()
    source_package = _package_root(source_root)
    _ensure_private_directory(runtime_dir)
    runtime_script = runtime_dir / "proofgate_plugin.py"
    _atomic_copy(Path(__file__).resolve(), runtime_script, 0o700)
    for filename in _RUNTIME_PACKAGE_FILES:
        _atomic_copy(
            source_package / filename,
            runtime_dir / "completion_verifier" / filename,
            0o600,
        )
    return runtime_script


def _hook_command(runtime_script: Path) -> str:
    return " ".join(
        (
            shlex.quote(sys.executable),
            shlex.quote(str(runtime_script)),
            "hook",
        )
    )


def _installed_hook_command(runtime_path: Path) -> str:
    metadata_path = runtime_path / "installation.json"
    try:
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return _hook_command(runtime_path / "proofgate_plugin.py")
    command = value.get("hook_command") if isinstance(value, dict) else None
    if isinstance(command, str) and command:
        return command
    return _hook_command(runtime_path / "proofgate_plugin.py")


def _install(hooks_file: Path | None, runtime_dir: Path | None) -> int:
    hooks_path = _hooks_path(hooks_file)
    runtime_path = _runtime_path(runtime_dir)
    runtime_script = _copy_runtime(runtime_path)
    command = _hook_command(runtime_script)
    _atomic_write_json(
        runtime_path / "installation.json",
        {"hook_command": command, "runtime_script": str(runtime_script)},
    )
    uninstall_hooks(hooks_path)
    install_hooks(hooks_path, command=command)
    print(f"ProofGate runtime installed: {runtime_path}")
    print(f"Codex hooks installed: {hooks_path}")
    print("Review and trust the hooks with /hooks, then start a new task.")
    return 0


def _status(hooks_file: Path | None, runtime_dir: Path | None) -> int:
    hooks_path = _hooks_path(hooks_file)
    runtime_path = _runtime_path(runtime_dir)
    runtime_script = runtime_path / "proofgate_plugin.py"
    installed = runtime_script.is_file() and hooks_installed(
        hooks_path, command=_installed_hook_command(runtime_path)
    )
    print(f"ProofGate hooks: {'installed' if installed else 'not installed'}")
    print(f"Hooks file: {hooks_path}")
    print(f"Runtime: {runtime_path}")
    return 0 if installed else 1


def _uninstall(hooks_file: Path | None, runtime_dir: Path | None) -> int:
    hooks_path = _hooks_path(hooks_file)
    runtime_path = _runtime_path(runtime_dir)
    uninstall_hooks(hooks_path, command=_installed_hook_command(runtime_path))
    print(f"ProofGate handlers removed: {hooks_path}")
    print("The owner-only runtime and receipts were preserved for recovery.")
    return 0


def _hook() -> int:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise CodexIntegrationError(f"invalid Codex hook input: {error}") from error
    if not isinstance(input_data, dict):
        raise CodexIntegrationError("Codex hook input must be a JSON object")
    values = dict(os.environ)
    values[ALL_PROJECTS_ENV] = "1"
    output = handle_codex_hook(input_data, values)
    if output is not None:
        print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage the ProofGate Codex plugin")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "status", "uninstall"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("--hooks-file", type=Path)
        command_parser.add_argument("--runtime-dir", type=Path)
    subparsers.add_parser("hook", help=argparse.SUPPRESS)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "install":
            return _install(args.hooks_file, args.runtime_dir)
        if args.command == "status":
            return _status(args.hooks_file, args.runtime_dir)
        if args.command == "uninstall":
            return _uninstall(args.hooks_file, args.runtime_dir)
        if args.command == "hook":
            return _hook()
    except (CodexIntegrationError, OSError, RuntimeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
