# ProofGate Codex plugin

Status: implemented local plugin prototype

## Product boundary

ProofGate verifies whether positive execution claims in a Codex final response are supported by command evidence observed in the same turn. It does not inspect code quality, rerun commands, or prove broader correctness.

The plugin contains:

- `.codex-plugin/plugin.json`: plugin identity and Codex UI metadata;
- `skills/proofgate/SKILL.md`: safe enable, status, and disable workflow;
- `scripts/proofgate_plugin.py`: dependency-free runtime installer and hook entry point;
- `src/completion_verifier/`: the shared verification engine.

## Why activation is separate

The current Codex plugin loader installs skills, MCP servers, and apps, but does not automatically contribute a plugin's lifecycle hooks to the active hook registry. ProofGate therefore performs a one-time, explicit activation:

```bash
python3 scripts/proofgate_plugin.py install
```

Activation requires user approval because it changes user-level Codex configuration. It:

1. copies an allowlisted, standard-library-only runtime to `~/.local/share/proofgate/runtime`;
2. writes files and state directories with owner-only permissions;
3. safely merges ProofGate handlers into `~/.codex/hooks.json`;
4. replaces legacy Completion Verifier handlers to prevent duplicate evaluation while preserving unrelated hooks;
5. enables the hook across projects without a repository config file.

The stable runtime copy avoids hook commands pointing at a versioned plugin cache directory that may disappear during an update. Re-running activation atomically refreshes the runtime and does not duplicate handlers.

## Commands

```bash
python3 scripts/proofgate_plugin.py install
python3 scripts/proofgate_plugin.py status
python3 scripts/proofgate_plugin.py uninstall
```

For isolated testing, `--hooks-file` and `--runtime-dir` override both destinations. `PROOFGATE_HOOKS_FILE`, `PROOFGATE_RUNTIME_DIR`, and `XDG_DATA_HOME` provide environment-based overrides.

`uninstall` removes only the exact ProofGate handlers. It intentionally preserves runtime files and receipts; no recursive deletion is performed.

## Hook behavior

- `PostToolUse` records redacted `Bash` command evidence.
- `Stop` avoids a model call when the answer has no positive execution-claim keyword.
- Relevant answers are matched against at most 20 same-turn evidence items by an ephemeral, read-only `codex exec`.
- The nested process disables hooks, user configuration, and repository access.
- Unsupported claims block Stop once with the missing evidence.
- Matcher errors are recorded as `UNPROVEN` and never upgraded to supported.

The matcher reuses the Codex CLI's existing saved authentication. ProofGate does not read or copy authentication files.

## Update boundary

After a plugin update:

1. run the activation command again to refresh the stable runtime;
2. review `/hooks` if Codex reports a changed trust hash;
3. start a new task before testing the updated plugin skill.

Marketplace publication and a live OAuth dogfood run remain separate release steps.
