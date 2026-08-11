# Completion Verifier competitive and overlap research

Date: 2026-08-11

## Decision

The problem is real, but the original positioning is not unique enough to justify implementation unchanged.

- Continue validating the four-state, multi-evidence contract.
- Do not publish under the former `ProofGate` working name. The name is already used by multiple agent-guardrail products, and the Python package name is occupied.
- Do not position the project merely as “a receipt before an agent can say done.” `agent-done-or-not` already implements that proposition directly and in depth.
- The remaining defensible wedge is a small, agent-independent postcondition gate that evaluates heterogeneous evidence with explicit `PASS`, `FAIL`, `UNPROVEN`, and `BLOCKED` semantics.

This is a product-validation conclusion, not a trademark determination.

## Closest overlaps

| Tool | What its own documentation says it does | Overlap | Gap that may remain |
| --- | --- | --- | --- |
| [agent-done-or-not](https://github.com/mohamedzhioua/agent-done-or-not) | Captures command output, exit code, time, Git state, and hashes in fresh receipts; gates agent completion; audits claims; supports policy, CI, pre-commit, Claude, Cursor, and Codex | Very high | Its policy is primarily a set of required command receipts. It does not present a general four-state contract across file, HTTP, Git, and command observations. |
| [Distill](https://www.distillagent.dev/) | An evidence-first agent runtime whose task contracts can require files, HTTP services, and database mutations before releasing an answer | High at the concept level | It is a full agent runtime with memory, tools, skills, and chat surfaces, rather than a small standalone verifier usable with any agent or CI. |
| [TruthGuard](https://github.com/spyrae/truthguard) | Hooks into agent tool calls, checks exit codes and file checksums, auto-runs tests before commits, and blocks dangerous commands | Medium | It focuses on real-time agent hooks and predefined failure modes, not a portable completion-condition contract and receipt format. |
| [proofguard](https://github.com/mohamedzhioua/proofguard) | Provides kill-tested prompt and deterministic guards for evidence, secrets, dependencies, docs drift, and diff scope | Medium | It is a broader repository-policy guard suite. Its evidence-before-done behavior is partly a cooperating-agent instruction rather than the whole product being a standalone evidence evaluator. |
| [Dagger Checks](https://docs.dagger.io/core-concepts/checks/) | Runs programmable, local/CI checks and returns non-zero when a check fails | Medium | It is a workflow execution engine with pass/fail checks; it does not distinguish a disproven condition from missing, stale, or blocked evidence. |
| [Conftest](https://www.conftest.dev/) | Evaluates Rego policy against structured configuration data | Low to medium | It is a policy evaluator, not an evidence collector, freshness judge, or completion receipt generator. |
| [Cucumber](https://cucumber.io/docs/) | Executes plain-language specifications and reports whether software matches the scenarios | Low to medium | It expresses and runs behavioral tests, but does not bind heterogeneous observations and their freshness to an agent completion claim. |
| [in-toto Attestation](https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md) and [SLSA provenance](https://slsa.dev/spec/v1.2/provenance) | Standardize statements and provenance about software artifacts and builds | Adjacent | They are useful receipt/provenance models, but they do not decide whether a user-defined completion claim is currently proven. |
| [OpenAI Evals](https://github.com/openai/evals) | Evaluates models and LLM systems against benchmarks and custom evals | Adjacent | It measures system behavior across evaluation cases; it is not a local runtime gate for a particular work item’s claimed postconditions. |

## Name and distribution collision

There are at least two material name collisions:

1. [proofgate.dev](https://proofgate.dev/) describes “deterministic consequence rails” for agents, including policy gates, signed decisions, signed approvals, receipts, and audit logs before external actions execute. Its site also advertises `npm i proofgate`.
2. [PyPI `proofgate`](https://pypi.org/project/proofgate/) is an active Python package for blockchain transaction guardrails for AI agents. PyPI lists releases `0.1.0` and `0.1.1` from 2026-02-03.

Consequences:

- `proofgate` is unavailable as the intended PyPI distribution name.
- The project name would cause search, installation, and product-category confusion even if a different package name were used.
- Rename research is required before a public repository, package metadata, domain, or README branding is finalized.

## What the closest competitor changes in the design

`agent-done-or-not` has already validated and implemented several requirements that should be treated as baseline, not differentiation:

- evidence must be freshly re-executed rather than merely asserted;
- command output alone is not enough without exit status and capture time;
- evidence should be bound to Git commit/tree/dirty state;
- stale, missing, malformed, or already-consumed evidence must not silently pass;
- a hash proves what bytes were captured, not semantic correctness or who produced them;
- CI should run a pinned verifier rather than trusting verifier code from an untrusted change.

The minimum contract should therefore test a different claim:

> Can one small declarative gate consistently distinguish negative evidence, insufficient evidence, and an inability to verify across multiple observable surfaces?

## Proposed narrow positioning

Working description, pending rename:

> A local-first postcondition gate that turns commands, files, Git state, and HTTP observations into explicit PASS, FAIL, UNPROVEN, or BLOCKED receipts.

The product is not:

- a coding agent or agent loop;
- a test runner or CI engine;
- a prompt guard or policy pack;
- a model benchmark or LLM judge;
- an action-authorization system;
- a signed software-supply-chain attestation system in v0.1.

## Go/no-go criteria before the first public release

Proceed only if the vertical prototype demonstrates all of the following:

1. A stale artifact becomes `UNPROVEN`, not `PASS` or `FAIL`.
2. A missing artifact becomes `FAIL` because the negative condition was directly observed.
3. An unavailable executable or inaccessible target becomes `BLOCKED` without being mislabeled as a product failure.
4. One contract can combine command and file results into a deterministic overall verdict.
5. The receipt contains enough time and source-state context to expose reuse of old evidence.
6. The workflow is materially simpler than adopting an agent runtime or CI engine.

If the prototype collapses back to command receipts plus a stop hook, the project should contribute to or integrate `agent-done-or-not` instead of becoming another standalone tool.
