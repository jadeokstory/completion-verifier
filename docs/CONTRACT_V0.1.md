# Minimal `completion-verifier.yml` contract

Status: implemented vertical prototype

`Completion Verifier` is the descriptive working name. Public branding can be chosen after the vertical prototype validates the product distinction.

## Minimal example

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

## Decisions

### Contract boundary

- `version`, `gate`, and at least one `check` are required.
- Unknown fields are rejected. A typo must not silently weaken a gate.
- Check IDs are unique, stable identifiers matching `^[a-z][a-z0-9_-]{0,63}$`.
- Checks run in declaration order. v0.1 has no dependency graph or parallel execution contract.
- The configuration directory is the working directory and path base. This avoids dependence on the caller’s current directory.
- Every configured check is required. Optional/advisory checks are deferred until their effect on the overall verdict is specified.

### `command` check

- `command` is a non-empty argument vector, not a shell string.
- No shell is invoked. Pipes, redirects, interpolation, and `&&` are intentionally absent from v0.1.
- `timeout_seconds` is required and bounded to 1–86,400 seconds.
- Exit code zero is `PASS`.
- A non-zero exit, signal termination, or timeout is `FAIL`: the configured check ran but did not satisfy its contract.
- A missing executable or OS-level refusal to start it is `BLOCKED`: the verifier could not perform the check.
- A command skipped after an earlier fail-fast decision would be `UNPROVEN`. v0.1 should run all checks by default, so this case is reserved for future selection/fail-fast behavior.

The argument-vector form is intentionally less convenient than shell text. It gives the receipt an exact executable/argument contract, avoids platform-specific shell parsing, and reduces the risk of executing untrusted configuration through a shell.

### `file` check

- `path` is relative to the configuration directory. Absolute paths and parent traversal are invalid in v0.1.
- The target must be a regular file. A missing path or wrong file type is `FAIL` because the verifier directly observed that the condition is false.
- A permission or I/O error that prevents observation is `BLOCKED`.
- `freshness` is mandatory:
  - `run`: the file modification time must be at or after the gate run’s recorded start time;
  - `none`: existence is sufficient, and the author explicitly accepts pre-existing evidence.
- A regular file that exists but fails `freshness: run` is `UNPROVEN`, not `FAIL`: it may be a valid artifact, but it does not prove this run produced or revalidated it.
- `min_bytes` is optional and defaults conceptually to zero. A smaller observed file is `FAIL`.

`freshness: none` is deliberately explicit. Omitting freshness entirely is a schema error rather than an implicit acceptance of stale artifacts.

## Overall verdict

The gate verdict is deterministic using this precedence:

1. Any `FAIL` → overall `FAIL`.
2. Otherwise, any `BLOCKED` → overall `BLOCKED`.
3. Otherwise, any `UNPROVEN` → overall `UNPROVEN`.
4. All checks `PASS` → overall `PASS`.

`FAIL` has the highest precedence because one directly false required condition is enough to reject the completion claim even if another check could not run. `BLOCKED` precedes `UNPROVEN` because it identifies a concrete inability to verify rather than merely insufficient evidence.

## Schema versus runtime validation

The JSON Schema validates structure, types, allowed fields, relative-path syntax, and verifier-specific fields. The contract loader must additionally reject duplicate check IDs because JSON Schema cannot require uniqueness of one property across array items.

Schema validation errors are configuration errors, not gate verdicts. No receipt should claim `FAIL`, `UNPROVEN`, or `BLOCKED` for a contract that could not be parsed and validated.

## Deferred deliberately

- `git` and `http` check syntax
- environment variables and secret injection
- shell commands
- retries and flaky-test policy
- check selection, dependencies, and parallelism
- maximum-age freshness independent of the current run
- directories and glob matching
- optional checks and warning-only results
- receipt signing and attestation interoperability
- custom verifier plugins

These are not required to validate the first command-plus-file vertical flow.
