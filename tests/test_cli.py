import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from completion_verifier.cli import main


class CliTests(unittest.TestCase):
    def test_codex_project_management_uses_isolated_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            hooks_path = root / "hooks.json"
            state_path = root / "state"
            env = {"COMPLETION_VERIFIER_STATE_DIR": str(state_path)}

            with patch.dict(os.environ, env, clear=False):
                with redirect_stdout(StringIO()):
                    self.assertEqual(
                        main(
                            [
                                "codex",
                                "enable",
                                "--root",
                                str(root),
                                "--hooks-file",
                                str(hooks_path),
                            ]
                        ),
                        0,
                    )
                status = StringIO()
                with redirect_stdout(status):
                    self.assertEqual(
                        main(
                            [
                                "codex",
                                "status",
                                "--root",
                                str(root),
                                "--hooks-file",
                                str(hooks_path),
                            ]
                        ),
                        0,
                    )
                self.assertIn("Codex hooks: installed", status.getvalue())
                self.assertIn("Current project: enabled", status.getvalue())

                with redirect_stdout(StringIO()):
                    self.assertEqual(
                        main(["codex", "disable", "--root", str(root)]), 0
                    )
                    self.assertEqual(
                        main(
                            [
                                "codex",
                                "uninstall",
                                "--hooks-file",
                                str(hooks_path),
                            ]
                        ),
                        0,
                    )

            hooks = json.loads(hooks_path.read_text(encoding="utf-8"))["hooks"]
            self.assertNotIn("PostToolUse", hooks)
            self.assertNotIn("Stop", hooks)

    def test_init_refuses_to_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "completion-verifier.yml"
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["init", "--path", str(path)]), 0)
            stderr = StringIO()
            with redirect_stderr(stderr):
                self.assertEqual(main(["init", "--path", str(path)]), 2)

        self.assertIn("already exists", stderr.getvalue())

    def test_run_writes_receipts_and_strict_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "completion-verifier.yml"
            contract.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "gate": "release-ready",
                        "checks": [
                            {
                                "id": "tests",
                                "type": "command",
                                "command": [sys.executable, "-c", "print('ok')"],
                                "timeout_seconds": 5,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            stdout = StringIO()
            with redirect_stdout(stdout):
                exit_code = main(["run", "--config", str(contract), "--strict"])

            json_receipt = root / ".completion-verifier" / "receipt.json"
            markdown_receipt = root / ".completion-verifier" / "receipt.md"
            receipt = json.loads(json_receipt.read_text(encoding="utf-8"))

            self.assertEqual(exit_code, 0)
            self.assertEqual(receipt["verdict"], "PASS")
            self.assertTrue(markdown_receipt.exists())
            self.assertEqual(json_receipt.stat().st_mode & 0o777, 0o600)
            self.assertIn("release-ready: PASS", stdout.getvalue())

            report = StringIO()
            with redirect_stdout(report):
                self.assertEqual(
                    main(["report", "--receipt", str(json_receipt)]), 0
                )
            self.assertIn("# release-ready: PASS", report.getvalue())

    def test_non_pass_only_fails_in_strict_mode(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = root / "completion-verifier.yml"
            contract.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "gate": "release-ready",
                        "checks": [
                            {
                                "id": "tests",
                                "type": "command",
                                "command": [sys.executable, "-c", "raise SystemExit(1)"],
                                "timeout_seconds": 5,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()):
                self.assertEqual(main(["run", "--config", str(contract)]), 0)
                self.assertEqual(
                    main(["run", "--config", str(contract), "--strict"]), 1
                )

    def test_invalid_contract_is_configuration_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            contract = Path(directory) / "completion-verifier.yml"
            contract.write_text("version: 1\ngate: release-ready\n", encoding="utf-8")
            stderr = StringIO()
            with redirect_stderr(stderr):
                exit_code = main(["run", "--config", str(contract)])

        self.assertEqual(exit_code, 2)
        self.assertIn("invalid contract", stderr.getvalue())
