import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from completion_verifier.codex_integration import (
    ALL_PROJECTS_ENV,
    CODEX_MODEL_ENV,
    CodexIntegrationError,
    HOOK_COMMAND,
    NESTED_ENV,
    STATE_DIR_ENV,
    disable_project,
    enable_project,
    evaluate_claims_with_codex,
    handle_codex_hook,
    hooks_installed,
    install_hooks,
    latest_claim_receipt,
    project_enabled,
    uninstall_hooks,
)


def _post_event(root: Path, turn_id: str = "turn-1") -> dict[str, object]:
    return {
        "session_id": "session-1",
        "turn_id": turn_id,
        "cwd": str(root),
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_use_id": "tool-1",
        "tool_input": {"command": "python -m pytest"},
        "tool_response": {"exit_code": 0, "output": "33 passed"},
    }


def _stop_event(
    root: Path, message: str, turn_id: str = "turn-1"
) -> dict[str, object]:
    return {
        "session_id": "session-1",
        "turn_id": turn_id,
        "cwd": str(root),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
        "last_assistant_message": message,
    }


class CodexHookTests(unittest.TestCase):
    def test_all_projects_mode_does_not_require_project_enable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {
                STATE_DIR_ENV: str(root / "state"),
                ALL_PROJECTS_ENV: "1",
            }

            self.assertIsNone(handle_codex_hook(_post_event(root), env))
            receipt_paths = list((root / "state").rglob("events.jsonl"))
            self.assertEqual(len(receipt_paths), 1)

    def test_enable_and_disable_are_per_project(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {STATE_DIR_ENV: str(root / "state")}

            self.assertFalse(project_enabled(root, env))
            enable_project(root, env)
            self.assertTrue(project_enabled(root, env))
            disable_project(root, env)
            self.assertFalse(project_enabled(root, env))

    def test_post_tool_evidence_supports_stop_claim(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {STATE_DIR_ENV: str(root / "state")}
            enable_project(root, env)
            self.assertIsNone(handle_codex_hook(_post_event(root), env))
            seen: dict[str, object] = {}

            def evaluator(message, evidence, evaluator_env):
                seen["message"] = message
                seen["evidence"] = evidence
                return {
                    "verdict": "SUPPORTED",
                    "claims": [
                        {
                            "claim": "33 tests passed",
                            "status": "SUPPORTED",
                            "evidence_ids": ["tool-1"],
                            "reason": "pytest exited 0 and reported 33 passed",
                        }
                    ],
                    "summary": "The execution claim is supported.",
                }

            output = handle_codex_hook(
                _stop_event(root, "All 33 tests passed."), env, evaluator
            )

            self.assertIsNone(output)
            evidence = seen["evidence"]
            self.assertEqual(len(evidence), 1)
            self.assertEqual(evidence[0]["exit_code"], 0)
            self.assertIn("33 passed", evidence[0]["output_summary"])
            receipt = latest_claim_receipt(root, env)
            self.assertEqual(receipt["verdict"], "SUPPORTED")

    def test_unsupported_claim_blocks_stop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {STATE_DIR_ENV: str(root / "state")}
            enable_project(root, env)

            def evaluator(message, evidence, evaluator_env):
                return {
                    "verdict": "UNSUPPORTED",
                    "claims": [
                        {
                            "claim": "changes were pushed",
                            "status": "UNSUPPORTED",
                            "evidence_ids": [],
                            "reason": "no git push command was recorded",
                        }
                    ],
                    "summary": "The push claim is unsupported.",
                }

            output = handle_codex_hook(
                _stop_event(root, "Changes were pushed."), env, evaluator
            )

            self.assertEqual(output["decision"], "block")
            self.assertIn("no git push command", output["reason"])

    def test_non_execution_message_does_not_start_codex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {STATE_DIR_ENV: str(root / "state")}
            enable_project(root, env)

            def evaluator(message, evidence, evaluator_env):
                self.fail("evaluator should not run")

            output = handle_codex_hook(
                _stop_event(root, "The relevant file is src/app.py."), env, evaluator
            )

            self.assertIsNone(output)
            receipt = latest_claim_receipt(root, env)
            self.assertEqual(receipt["verdict"], "NO_VERIFIABLE_CLAIM")
            self.assertEqual(receipt["evaluator"], "local-prefilter")

    def test_nested_and_repeated_stop_hooks_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {STATE_DIR_ENV: str(root / "state")}
            enable_project(root, env)
            nested_env = dict(env)
            nested_env[NESTED_ENV] = "1"
            self.assertIsNone(
                handle_codex_hook(
                    _stop_event(root, "Tests passed."), nested_env
                )
            )
            repeated = _stop_event(root, "Tests passed.")
            repeated["stop_hook_active"] = True
            self.assertIsNone(handle_codex_hook(repeated, env))

    def test_evidence_is_redacted_before_storage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / "state"
            env = {STATE_DIR_ENV: str(state)}
            enable_project(root, env)
            secret = "value" * 5
            event = _post_event(root)
            event["tool_response"] = {
                "exit_code": 0,
                "output": f"API_KEY={secret}",
            }

            handle_codex_hook(event, env)

            stored = "\n".join(
                path.read_text(encoding="utf-8")
                for path in state.rglob("events.jsonl")
            )
            self.assertNotIn(secret, stored)
            self.assertIn("[REDACTED]", stored)


class CodexHookInstallerTests(unittest.TestCase):
    def test_custom_hook_command_can_be_managed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hooks_path = Path(directory) / "hooks.json"
            command = "/private/runtime/proofgate_plugin.py hook"

            install_hooks(hooks_path, command=command)
            self.assertTrue(hooks_installed(hooks_path, command=command))
            self.assertFalse(hooks_installed(hooks_path))
            uninstall_hooks(hooks_path, command=command)
            self.assertFalse(hooks_installed(hooks_path, command=command))

    def test_install_is_idempotent_and_uninstall_preserves_other_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            hooks_path = Path(directory) / "hooks.json"
            hooks_path.write_text(
                json.dumps(
                    {
                        "description": "existing",
                        "hooks": {
                            "Stop": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "other-tool stop",
                                        }
                                    ]
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )

            install_hooks(hooks_path)
            install_hooks(hooks_path)
            document = json.loads(hooks_path.read_text(encoding="utf-8"))

            self.assertTrue(hooks_installed(hooks_path))
            handlers = [
                handler
                for groups in document["hooks"].values()
                for group in groups
                for handler in group["hooks"]
                if handler.get("command") == HOOK_COMMAND
            ]
            self.assertEqual(len(handlers), 2)

            uninstall_hooks(hooks_path)
            document = json.loads(hooks_path.read_text(encoding="utf-8"))
            self.assertFalse(hooks_installed(hooks_path))
            self.assertEqual(
                document["hooks"]["Stop"][0]["hooks"][0]["command"],
                "other-tool stop",
            )


class CodexEvaluatorTests(unittest.TestCase):
    def test_codex_output_schema_uses_supported_subset(self) -> None:
        schema_path = (
            Path(__file__).parents[1]
            / "src"
            / "completion_verifier"
            / "claim-evaluation.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))

        self.assertNotIn("uniqueItems", json.dumps(schema))

    def test_codex_exec_is_ephemeral_read_only_and_hooks_are_disabled(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "claims": [
                        {
                            "claim": "tests passed",
                            "status": "SUPPORTED",
                            "evidence_ids": ["tool-1"],
                            "reason": "matching evidence",
                        }
                    ],
                    "summary": "supported",
                }
            ),
            stderr="",
        )
        env = dict(os.environ)
        env[CODEX_MODEL_ENV] = "test-model"
        with patch(
            "completion_verifier.codex_integration.subprocess.run",
            return_value=completed,
        ) as run:
            result = evaluate_claims_with_codex(
                "Tests passed.", [{"evidence_id": "tool-1"}], env
            )

        command = run.call_args.args[0]
        self.assertEqual(result["verdict"], "SUPPORTED")
        self.assertIn("--ephemeral", command)
        self.assertIn("read-only", command)
        self.assertIn("hooks", command)
        self.assertIn("test-model", command)
        self.assertEqual(command[-1], "-")
        self.assertEqual(run.call_args.kwargs["env"][NESTED_ENV], "1")
        self.assertIn("Tests passed.", run.call_args.kwargs["input"])

    def test_codex_cannot_support_a_claim_with_unknown_evidence(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps(
                {
                    "verdict": "SUPPORTED",
                    "claims": [
                        {
                            "claim": "tests passed",
                            "status": "SUPPORTED",
                            "evidence_ids": ["invented"],
                            "reason": "matching evidence",
                        }
                    ],
                    "summary": "supported",
                }
            ),
            stderr="",
        )
        with patch(
            "completion_verifier.codex_integration.subprocess.run",
            return_value=completed,
        ):
            with self.assertRaisesRegex(CodexIntegrationError, "not provided"):
                evaluate_claims_with_codex(
                    "Tests passed.", [{"evidence_id": "tool-1"}], dict(os.environ)
                )
