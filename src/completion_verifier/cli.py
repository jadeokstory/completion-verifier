import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import __version__
from .codex_integration import (
    CodexIntegrationError,
    default_hooks_file,
    disable_project,
    enable_project,
    handle_codex_hook,
    hooks_installed,
    install_hooks,
    latest_claim_receipt,
    project_enabled,
    resolve_project_root,
    uninstall_hooks,
)
from .contract import ContractError, DEFAULT_CONFIG_NAME, load_contract
from .receipt import (
    DEFAULT_RECEIPT_DIR,
    JSON_RECEIPT_NAME,
    render_markdown,
    write_receipts,
)
from .runner import run_contract
from .verdict import Verdict


_TEMPLATE = """version: 1
gate: release-ready
checks:
  - id: tests
    type: command
    command: [python3, -m, pytest]
    timeout_seconds: 120
  - id: artifact
    type: file
    path: dist/app.tar.gz
    freshness: run
    min_bytes: 1
"""


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="completion-verifier",
        description="Verify completion claims against observable evidence.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_parser = subparsers.add_parser("init", help="create a starter contract")
    init_parser.add_argument("--path", type=Path, default=Path(DEFAULT_CONFIG_NAME))

    run_parser = subparsers.add_parser("run", help="run all configured checks")
    run_parser.add_argument("--config", type=Path, default=Path(DEFAULT_CONFIG_NAME))
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        help=f"receipt directory relative to the contract (default: {DEFAULT_RECEIPT_DIR})",
    )
    run_parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero unless the overall verdict is PASS",
    )

    report_parser = subparsers.add_parser("report", help="render an existing receipt")
    report_parser.add_argument(
        "--receipt",
        type=Path,
        default=Path(DEFAULT_RECEIPT_DIR) / JSON_RECEIPT_NAME,
    )
    report_parser.add_argument(
        "--format", choices=("markdown", "json"), default="markdown"
    )

    codex_parser = subparsers.add_parser(
        "codex", help="manage automatic Codex execution-claim verification"
    )
    codex_subparsers = codex_parser.add_subparsers(
        dest="codex_command", required=True
    )
    for command_name in ("enable", "status"):
        command_parser = codex_subparsers.add_parser(command_name)
        command_parser.add_argument("--root", type=Path, default=Path.cwd())
        command_parser.add_argument("--hooks-file", type=Path)
    disable_parser = codex_subparsers.add_parser("disable")
    disable_parser.add_argument("--root", type=Path, default=Path.cwd())
    uninstall_parser = codex_subparsers.add_parser("uninstall")
    uninstall_parser.add_argument("--hooks-file", type=Path)

    hook_parser = subparsers.add_parser("hook", help=argparse.SUPPRESS)
    hook_subparsers = hook_parser.add_subparsers(dest="hook_target", required=True)
    hook_subparsers.add_parser("codex")
    return parser


def _init(path: Path) -> int:
    try:
        with path.open("x", encoding="utf-8") as file_handle:
            file_handle.write(_TEMPLATE)
    except FileExistsError:
        print(f"error: contract already exists: {path}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"error: cannot create contract {path}: {error}", file=sys.stderr)
        return 2
    print(f"created {path}")
    return 0


def _run(config: Path, output_dir: Path | None, strict: bool) -> int:
    contract = load_contract(config)
    receipt = run_contract(contract)
    receipt_dir = output_dir or Path(DEFAULT_RECEIPT_DIR)
    if not receipt_dir.is_absolute():
        receipt_dir = contract.root / receipt_dir
    json_path, markdown_path = write_receipts(receipt, receipt_dir)

    print(f"{receipt['gate']}: {receipt['verdict']}")
    for check in receipt["checks"]:
        marker = {"PASS": "✓", "FAIL": "✗", "UNPROVEN": "?", "BLOCKED": "!"}[
            check["verdict"]
        ]
        print(f"{marker} {check['id']:<16} {check['verdict']:<10} {check['reason']}")
    print(f"JSON receipt: {json_path}")
    print(f"Markdown receipt: {markdown_path}")

    if strict and receipt["verdict"] != Verdict.PASS.value:
        return 1
    return 0


def _report(receipt_path: Path, output_format: str) -> int:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        print(f"error: cannot read receipt {receipt_path}: {error}", file=sys.stderr)
        return 2
    if output_format == "json":
        print(json.dumps(receipt, indent=2, ensure_ascii=False))
    else:
        try:
            print(render_markdown(receipt), end="")
        except (KeyError, TypeError) as error:
            print(f"error: malformed receipt {receipt_path}: {error}", file=sys.stderr)
            return 2
    return 0


def _codex_enable(root: Path, hooks_file: Path | None) -> int:
    hooks_path = install_hooks(hooks_file)
    project_root = enable_project(root)
    print(f"Codex hooks installed: {hooks_path}")
    print(f"Completion verification enabled: {project_root}")
    print("Review and trust the hooks with /hooks in Codex, then start a new task.")
    return 0


def _codex_status(root: Path, hooks_file: Path | None) -> int:
    project_root = resolve_project_root(root)
    hooks_path = hooks_file or default_hooks_file()
    installed = hooks_installed(hooks_path)
    enabled = project_enabled(project_root)
    print(f"Codex hooks: {'installed' if installed else 'not installed'} ({hooks_path})")
    print(
        "Current project: "
        f"{'enabled' if enabled else 'disabled'} ({project_root})"
    )
    receipt = latest_claim_receipt(project_root)
    if receipt:
        print(
            "Latest claim verdict: "
            f"{receipt.get('verdict', 'unknown')} ({receipt.get('evaluated_at', 'unknown')})"
        )
    else:
        print("Latest claim verdict: unavailable")
    return 0


def _codex_disable(root: Path) -> int:
    project_root = disable_project(root)
    print(f"Completion verification disabled: {project_root}")
    return 0


def _codex_uninstall(hooks_file: Path | None) -> int:
    hooks_path = uninstall_hooks(hooks_file)
    print(f"Completion Verifier handlers removed: {hooks_path}")
    return 0


def _codex_hook() -> int:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        raise CodexIntegrationError(f"invalid Codex hook input: {error}") from error
    if not isinstance(input_data, dict):
        raise CodexIntegrationError("Codex hook input must be a JSON object")
    output = handle_codex_hook(input_data)
    if output is not None:
        print(json.dumps(output, ensure_ascii=False, separators=(",", ":")))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.subcommand == "init":
            return _init(args.path)
        if args.subcommand == "run":
            return _run(args.config, args.output_dir, args.strict)
        if args.subcommand == "report":
            return _report(args.receipt, args.format)
        if args.subcommand == "codex":
            if args.codex_command == "enable":
                return _codex_enable(args.root, args.hooks_file)
            if args.codex_command == "status":
                return _codex_status(args.root, args.hooks_file)
            if args.codex_command == "disable":
                return _codex_disable(args.root)
            if args.codex_command == "uninstall":
                return _codex_uninstall(args.hooks_file)
        if args.subcommand == "hook" and args.hook_target == "codex":
            return _codex_hook()
    except ContractError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except CodexIntegrationError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    raise AssertionError(f"unhandled subcommand: {args.subcommand}")
