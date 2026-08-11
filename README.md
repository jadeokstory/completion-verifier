# ProofGate

ProofGate is a Codex plugin and local-first CLI that checks an agent's completion claim against observable evidence.

It does not decide whether code “looks good.” Its Codex integration checks whether commands that Codex claims to have run were actually observed in the same turn. For stricter CI and release gates, it can also run checks declared in `completion-verifier.yml`.

## Codex plugin

The repository root is a valid `proofgate` Codex plugin. The plugin bundles its hook runtime, so users do not need to install the Python package or create `completion-verifier.yml` for automatic claim verification.

From a local checkout, activate the plugin runtime with:

```bash
python3 scripts/proofgate_plugin.py install
```

An installed plugin also includes a `proofgate` skill. Ask Codex to “Enable ProofGate” and it will run the same activation flow after requesting approval for the user-level configuration change.

Activation safely merges user-level `PostToolUse` and `Stop` handlers, installs an owner-only runtime under `~/.local/share/proofgate`, and enables verification across Codex projects. Open `/hooks` to review and trust the handlers, then start a new task.

Current Codex plugin loading does not activate plugin-local lifecycle hooks by itself, so this one-time activation is required. Re-run it after updating the plugin to refresh the bundled runtime.

Check or disable it with:

```bash
python3 scripts/proofgate_plugin.py status
python3 scripts/proofgate_plugin.py uninstall
```

`uninstall` removes only ProofGate's handlers. It preserves unrelated hooks, receipts, and the owner-only runtime for recovery. See [the plugin guide](docs/PLUGIN.md) for the packaging and trust boundary.

## Automatic Codex verification with the CLI

The Python package remains available for project-scoped installation and for strict contract checks. After installing it, enable automatic verification in the current project:

```bash
completion-verifier codex enable
```

This installs user-level `PostToolUse` and `Stop` hooks and enables them only for the current project. Open `/hooks` in Codex to review and trust the hook definition, then start a new task.

No `completion-verifier.yml` is required for this mode. The integration:

1. records redacted command evidence from `PostToolUse`;
2. gives every Stop message and a compact same-turn evidence bundle to an ephemeral, read-only `codex exec`;
3. allows supported messages and messages with no execution claim;
4. blocks unsupported claims until the report is corrected or new evidence is recorded.

It does not review code quality, rerun tests, or inspect the repository during claim matching. The nested Codex run starts in an empty temporary directory, ignores user configuration and rules, disables hooks, and uses the authentication already saved by the Codex CLI.

Check or change the current project setting:

```bash
completion-verifier codex status
completion-verifier codex disable
```

Remove only Completion Verifier's handlers from the user hook file:

```bash
completion-verifier codex uninstall
```

Local hook state and owner-only receipts are stored under `~/.local/state/completion-verifier` by default. Set `XDG_STATE_HOME` or `COMPLETION_VERIFIER_STATE_DIR` to choose another location. Set `COMPLETION_VERIFIER_CODEX_MODEL` to choose the model for the compact claim matcher and `COMPLETION_VERIFIER_CODEX_TIMEOUT_SECONDS` to change its 120-second timeout.

See [the Codex integration guide](docs/CODEX_HOOKS.md) for the exact evidence and verdict contract.

## Strict contract mode

The contract runner executes the checks you declared and reports one of four states:

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

### Quick start

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

### Contract rules

- Checks execute in declaration order.
- Commands are argument arrays and run without a shell.
- Commands must declare a timeout.
- File paths are relative to the contract and cannot escape its directory.
- `freshness: run` requires a file modified during the current gate run.
- `freshness: none` explicitly permits a pre-existing file.
- Unknown configuration fields and duplicate check IDs are rejected.

See [the full contract](docs/CONTRACT_V0.1.md) and the [published JSON Schema](schemas/completion-verifier.schema.json).

### Receipt trust boundary

Receipts record timestamps, working directory, Git state and porcelain-status fingerprints before and after the run, exact check outcomes, command/output hashes, file size/mtime/hash, and whether basic secret-shape redaction was applied. `changed_during_run` reports whether the observable Git state differs between those two snapshots.

The output hash is SHA-256 over the raw captured stdout bytes, a NUL separator, and the raw captured stderr bytes. It does not prove semantic correctness, authorship, or resistance to a malicious local process. Redaction covers common secret shapes, including AWS credential assignments, database URL assignments, bearer tokens, and URI passwords, but cannot guarantee that arbitrary sensitive output is recognized. Commands should avoid printing secrets.

## Non-goals for this prototype

- code-quality or semantic-correctness review;
- automatically rerunning missing commands or fixing failures;
- action authorization or human approval workflows;
- signed attestations;
- shell pipelines, retries, or verifier plugins;
- `git` and `http` checks, which remain planned for later v0.1 work.

## Test

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```
