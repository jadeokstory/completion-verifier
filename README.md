# Completion Verifier

Completion Verifier is a local-first CLI that checks an agent's completion claim against observable postconditions.

It does not decide whether code “looks good.” It runs the checks you declared and reports one of four states:

- `PASS`: every required condition was directly confirmed;
- `FAIL`: a required condition was directly observed to be false;
- `UNPROVEN`: available evidence is missing or too old to prove this run;
- `BLOCKED`: the environment prevented a verifier from performing its observation.

The current vertical prototype supports `command` and `file` checks, JSON and Markdown receipts, output redaction, and strict CI exit behavior.

## Install for development

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

Python 3.10 or newer is required.

## Quick start

Create a starter contract:

```bash
completion-verifier init
```

Edit `completion-verifier.yml` so its checks describe the evidence your completion claim actually needs:

```yaml
version: 1
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
```

Run the gate:

```bash
completion-verifier run
```

Receipts are written atomically with owner-only permissions to:

```text
.completion-verifier/receipt.json
.completion-verifier/receipt.md
```

Use strict mode in CI. It exits `1` for `FAIL`, `UNPROVEN`, or `BLOCKED` and exits `0` only for `PASS`:

```bash
completion-verifier run --strict
```

Without `--strict`, a completed verification run exits `0` regardless of its verdict so local users can inspect the receipt. Invalid configuration or receipt I/O exits `2` in both modes.

Render the latest receipt:

```bash
completion-verifier report
completion-verifier report --format json
```

## Contract rules

- Checks execute in declaration order.
- Commands are argument arrays and run without a shell.
- Commands must declare a timeout.
- File paths are relative to the contract and cannot escape its directory.
- `freshness: run` requires a file modified during the current gate run.
- `freshness: none` explicitly permits a pre-existing file.
- Unknown configuration fields and duplicate check IDs are rejected.

See [the full contract](docs/CONTRACT_V0.1.md) and the [published JSON Schema](schemas/completion-verifier.schema.json).

## Receipt trust boundary

Receipts record timestamps, working directory, Git state before and after the run, exact check outcomes, command/output hashes, file size/mtime/hash, and whether basic secret-shape redaction was applied.

A hash binds the receipt to captured bytes; it does not prove semantic correctness, authorship, or resistance to a malicious local process. Redaction covers common secret shapes but cannot guarantee that arbitrary sensitive output is recognized. Commands should avoid printing secrets.

## Non-goals for this prototype

- running an AI agent or orchestration loop;
- LLM-as-judge evaluation;
- action authorization or human approval workflows;
- signed attestations;
- shell pipelines, retries, or verifier plugins;
- `git` and `http` checks, which remain planned for later v0.1 work.

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
