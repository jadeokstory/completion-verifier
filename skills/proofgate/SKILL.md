---
name: proofgate
description: Install, inspect, or disable ProofGate's automatic Codex execution-claim verification. Use when the user asks to enable ProofGate, check whether it is active, disable its hooks, or explain what ProofGate verified.
---

# ProofGate

ProofGate checks one narrow fact: when Codex says a command, test, build, push, deployment, or similar action ran or succeeded, was matching command evidence observed in the same turn?

It does not review code quality, rerun commands, or prove broader product correctness.

## Paths

- `skill_dir`: the directory containing this `SKILL.md`.
- `plugin_root`: two directories above `skill_dir`.
- Management script: `<plugin_root>/scripts/proofgate_plugin.py`.

Resolve the real absolute `plugin_root` before executing a management command. Do not assume the current working directory is the plugin root.

## Enable

Enabling writes an owner-only runtime under `~/.local/share/proofgate` and safely merges two handlers into `~/.codex/hooks.json`. Because this changes user-level Codex configuration, obtain the user's approval immediately before running:

```bash
python3 <plugin_root>/scripts/proofgate_plugin.py install
```

After success, tell the user to open `/hooks`, review and trust the handlers, and start a new task. Do not claim ProofGate is active until the install command succeeds.

## Status

Status is read-only and does not require approval:

```bash
python3 <plugin_root>/scripts/proofgate_plugin.py status
```

Report the command's observed result. Do not infer installation merely from the plugin being present; current Codex plugin loading does not activate plugin-local lifecycle hooks automatically.

## Disable

Disabling removes only ProofGate's handlers and preserves unrelated hooks, the runtime, and receipts. Because it changes user-level Codex configuration, obtain the user's approval immediately before running:

```bash
python3 <plugin_root>/scripts/proofgate_plugin.py uninstall
```

## Privacy and authentication

- Never read or print authentication files, tokens, cookies, or secret environment values.
- ProofGate uses the Codex CLI's existing saved authentication for its compact `codex exec` matcher.
- Command text and output excerpts are redacted on a best-effort basis before persistence or model evaluation.
- The matcher receives only the last assistant message and at most 20 same-turn evidence items.
- A matcher failure is `UNPROVEN`, never `SUPPORTED`.
