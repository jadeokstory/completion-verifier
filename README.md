# ProofGate

> Trust the evidence, not the completion claim.

ProofGate is an open-source Codex plugin and local-first CLI that checks whether an agent's execution claims are backed by observable evidence.

When Codex says that tests passed, a build completed, or a push succeeded, ProofGate checks for matching command evidence from the same turn. It does not decide whether the code is good or whether the product is correct.

> **Project status:** v0.1 prototype. The repository is public under the MIT License and ready for experimentation and contributions. Plugin marketplace publication and stable package distribution are not available yet; install from source for now.

## Why ProofGate?

An agent's final answer is a report, not proof. A command can fail while its output contains success-looking text, an old test result can be mistaken for current evidence, or a completion claim can be made without running anything at all.

ProofGate adds a narrow postcondition gate:

```text
Codex runs a command
  -> ProofGate records redacted, same-turn evidence

Codex prepares its final answer
  -> ProofGate matches execution claims to that evidence
     -> supported or no execution claim: allow
     -> unsupported or unproven: block and explain what is missing
```

## Two verification modes

| Mode | Best for | Behavior |
| --- | --- | --- |
| Codex plugin | Interactive agent sessions | Checks what Codex claims it ran against commands observed in the same turn |
| Contract runner | CI and release gates | Runs repository-owned checks declared in `completion-verifier.yml` and writes receipts |

The modes are complementary. The plugin verifies the report; the contract runner verifies required postconditions whether or not the agent mentioned them.

## Quick start: Codex plugin

Clone the repository and activate the bundled runtime:

```bash
git clone https://github.com/jadeokstory/completion-verifier.git
cd completion-verifier
python3 scripts/proofgate_plugin.py install
```

Then:

1. Open `/hooks` in Codex and review the `PostToolUse` and `Stop` handlers.
2. Trust the handlers when prompted.
3. Start a new Codex task.

No Python package installation or `completion-verifier.yml` is required for automatic claim verification. The plugin uses the authentication already saved by the Codex CLI; ProofGate does not read or copy authentication files.

Check or remove the integration:

```bash
python3 scripts/proofgate_plugin.py status
python3 scripts/proofgate_plugin.py uninstall
```

`uninstall` removes only ProofGate's handlers. It preserves unrelated hooks, verification receipts, and the owner-only runtime for recovery. Re-run `install` after updating the checkout to refresh the stable runtime.

See the [plugin guide](docs/PLUGIN.md) for packaging and activation details.

## What the Codex gate trusts

The automatic gate:

1. records redacted `Bash` command evidence from Codex `PostToolUse` events;
2. binds evidence to the current `session_id` and `turn_id`;
3. accepts an exit code only from Codex's structured session transcript when the session, turn, and exact command output match;
4. never treats exit-code-looking stdout as process status;
5. sends a bounded, redacted claim-and-evidence bundle to an ephemeral, read-only `codex exec` matcher;
6. keeps unsupported or unproven claims blocked until the report is corrected or new same-turn evidence appears.

Missing identifiers and unavailable trustworthy status fail closed. A Codex transcript-format change may therefore cause a claim to remain unproven, but it should not turn missing evidence into a successful verdict.

See the [Codex integration contract](docs/CODEX_HOOKS.md) for the complete evidence, evaluator, state, and recovery boundaries.

## Contract runner

The Python CLI is available for repository-owned checks and project-scoped Codex integration.

### Install from source

Python 3.10 or newer is required.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
```

### Create a contract

```bash
completion-verifier init
```

Edit `completion-verifier.yml` so it describes the evidence required for completion:

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

Receipts are written atomically with owner-only permissions:

```text
.completion-verifier/receipt.json
.completion-verifier/receipt.md
```

Use strict mode in CI. It exits `0` only for `PASS` and exits `1` for `FAIL`, `UNPROVEN`, or `BLOCKED`:

```bash
completion-verifier run --strict
```

Render an existing receipt:

```bash
completion-verifier report
completion-verifier report --format json
```

See the [minimal contract](docs/CONTRACT_V0.1.md) and [JSON Schema](schemas/completion-verifier.schema.json).

## Verdicts

| Verdict | Meaning |
| --- | --- |
| `PASS` | Every required condition was directly confirmed |
| `FAIL` | A required condition was directly observed to be false |
| `UNPROVEN` | Available evidence is insufficient or too old |
| `BLOCKED` | The environment prevented the verifier from observing the condition |

## Security and privacy

- Hook state and receipts are stored outside the repository with owner-only permissions by default.
- Raw command output is not persisted by the Codex integration. ProofGate stores a hash and a bounded, redacted excerpt.
- Common credential shapes—including quoted JSON fields, authorization headers, URI passwords, and private-key blocks—are redacted before storage or evaluation.
- The nested matcher runs ephemerally in a read-only sandbox, from an empty temporary directory, with user rules, MCP configuration, and hooks disabled.
- Redaction is best effort. Commands should still avoid printing secrets.
- Receipts are local observations, not signed attestations, and do not defend against a malicious process with the same local-user privileges.

## Scope and non-goals

ProofGate currently supports:

- same-turn Codex execution-claim verification;
- `command` and `file` contract checks;
- JSON and Markdown receipts;
- output redaction and strict CI exit behavior.

It does not currently provide:

- code-quality or semantic-correctness review;
- automatic reruns or failure repair;
- action authorization or human approval workflows;
- signed attestations;
- shell pipelines, retries, or third-party verifier plugins;
- `git` or `http` contract checks.

## Contributing

Issues, focused pull requests, documentation improvements, and additional adversarial test cases are welcome.

For a local development loop:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

Please keep changes narrow, add regression coverage for behavioral fixes, and document any change to the evidence or trust boundary. Do not include real credentials or private command output in fixtures, issues, or pull requests.

Good first contribution areas include:

- clearer installation and troubleshooting documentation;
- portable tests across supported Python versions;
- new secret-shape redaction fixtures using synthetic values;
- contract verifiers that preserve the local-first and observable-evidence model.

## Documentation

- [Codex plugin guide](docs/PLUGIN.md)
- [Codex hook contract](docs/CODEX_HOOKS.md)
- [Minimal YAML contract](docs/CONTRACT_V0.1.md)
- [Competitive and naming research](docs/COMPETITIVE_RESEARCH.md)
- [Project handoff and roadmap](docs/HANDOFF.md)

## License

[MIT](LICENSE) © jadeokstory
