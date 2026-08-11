# Automatic Codex execution-claim verification

Status: implemented prototype

This integration answers a narrow question:

> When Codex says that a command, test, build, lint, install, deployment, publication, or push ran or succeeded, was matching execution evidence observed in the same Codex turn?

It does not grade code quality or infer product correctness.

## Enable it

Install Completion Verifier so the `completion-verifier` command is on `PATH`, then run this from the project:

```bash
completion-verifier codex enable
```

The command safely merges two handlers into `~/.codex/hooks.json`:

- `PostToolUse`, matched to `Bash`, records command evidence;
- `Stop` compares the last assistant message with same-turn evidence.

It also records a per-project enable flag outside the repository. The global hooks immediately return for projects that are not enabled.

Codex requires non-managed hooks to be reviewed and trusted. Use `/hooks` after enabling the integration. A new or changed hook definition must be trusted again.

## Hook flow

```text
Codex command completes
  -> PostToolUse records redacted command, exit code, output hash, and output excerpt

Codex tries to stop
  -> no positive execution claim: allow without a model call
  -> positive execution claim: run compact read-only codex exec matcher
       -> SUPPORTED: allow
       -> NO_VERIFIABLE_CLAIM: allow
       -> UNSUPPORTED: block once and return the missing evidence to Codex
       -> evaluator error: mark UNPROVEN and block once
```

`stop_hook_active` prevents repeated blocking of the same turn. `COMPLETION_VERIFIER_NESTED=1` and `codex exec --disable hooks` prevent recursive verification.

## Evidence boundary

Only `Bash` evidence reported by Codex `PostToolUse` is considered. Unified execution commands use this hook path as `Bash`. Evidence is filtered to the current `turn_id`; an older command from another turn does not prove a new claim.

Each evidence item contains:

- evidence id;
- observed time;
- redacted command text;
- exit code when the tool response exposes one;
- SHA-256 of the raw tool response;
- a redacted, bounded output excerpt.

The raw tool response is not persisted. Common secret shapes are redacted before command text or excerpts are stored or sent to the matcher. Redaction is best effort; commands should still avoid printing secrets.

## Matcher boundary

The matcher receives only the redacted last assistant message and at most 20 same-turn evidence items. It runs with:

- an ephemeral Codex session;
- a read-only sandbox;
- an empty temporary working directory;
- user configuration, rules, MCP configuration, and hooks disabled;
- a strict JSON output schema.

The matcher returns:

- `SUPPORTED`: every positive execution claim has direct evidence;
- `UNSUPPORTED`: at least one positive execution claim lacks or contradicts evidence;
- `NO_VERIFIABLE_CLAIM`: the message contains no positive execution claim.

Evaluation failure is recorded as `UNPROVEN`; it is never silently upgraded to `SUPPORTED`.

## State and controls

The default state directory is:

```text
~/.local/state/completion-verifier
```

`XDG_STATE_HOME` changes the state parent. `COMPLETION_VERIFIER_STATE_DIR` overrides the complete path. Project roots and session identifiers are hashed for directory names; the project root is retained in its owner-only project record. Claim receipts store a hash of the assistant message and session id, compact claim results, and evidence metadata.

Commands:

```bash
completion-verifier codex status
completion-verifier codex disable
completion-verifier codex uninstall
```

`disable` affects only the current project. `uninstall` removes Completion Verifier's two handlers while preserving unrelated hooks in `~/.codex/hooks.json`.

Optional runtime settings:

```text
COMPLETION_VERIFIER_CODEX_BIN
COMPLETION_VERIFIER_CODEX_MODEL
COMPLETION_VERIFIER_CODEX_TIMEOUT_SECONDS
```

The timeout defaults to 120 seconds and accepts 1 through 900 seconds.

## Strict contracts remain optional

`completion-verifier.yml` is not used by automatic claim matching. Keep using the contract runner when a team needs stable, repository-owned release criteria:

```bash
completion-verifier run --strict
```

The two modes are complementary: the hook verifies what the agent says it ran, while the contract runner executes required postconditions regardless of what the agent claimed.
