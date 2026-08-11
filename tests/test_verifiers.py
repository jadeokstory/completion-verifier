import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from completion_verifier.verifiers.command import verify_command
from completion_verifier.verifiers.file import verify_file


class CommandVerifierTests(unittest.TestCase):
    def test_pass_and_redacted_evidence(self) -> None:
        assigned_value = "value" * 4
        with tempfile.TemporaryDirectory() as directory:
            result = verify_command(
                {
                    "id": "tests",
                    "type": "command",
                    "command": [
                        sys.executable,
                        "-c",
                        "print('API_KEY=' + 'value' * 4)",
                    ],
                    "timeout_seconds": 5,
                },
                Path(directory),
            )

        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["exit_code"], 0)
        self.assertTrue(result["evidence"]["redaction_applied"])
        self.assertNotIn(assigned_value, result["evidence"]["stdout"])
        self.assertEqual(len(result["evidence"]["output_sha256"]), 64)

    def test_nonzero_exit_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = verify_command(
                {
                    "id": "tests",
                    "type": "command",
                    "command": [sys.executable, "-c", "raise SystemExit(7)"],
                    "timeout_seconds": 5,
                },
                Path(directory),
            )

        self.assertEqual(result["verdict"], "FAIL")
        self.assertEqual(result["evidence"]["exit_code"], 7)

    def test_secret_shaped_command_argument_is_not_stored_verbatim(self) -> None:
        assigned_value = "value" * 4
        with tempfile.TemporaryDirectory() as directory:
            result = verify_command(
                {
                    "id": "tests",
                    "type": "command",
                    "command": [
                        sys.executable,
                        "-c",
                        "print('ok')",
                        "token=" + assigned_value,
                    ],
                    "timeout_seconds": 5,
                },
                Path(directory),
            )

        self.assertEqual(result["verdict"], "PASS")
        self.assertTrue(result["evidence"]["redaction_applied"])
        self.assertNotIn(
            assigned_value, " ".join(result["evidence"]["command"])
        )
        self.assertEqual(len(result["evidence"]["command_sha256"]), 64)

    def test_missing_executable_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = verify_command(
                {
                    "id": "tests",
                    "type": "command",
                    "command": ["completion-verifier-command-that-does-not-exist"],
                    "timeout_seconds": 5,
                },
                Path(directory),
            )

        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIsNone(result["evidence"]["exit_code"])

    def test_timeout_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = verify_command(
                {
                    "id": "tests",
                    "type": "command",
                    "command": [sys.executable, "-c", "import time; time.sleep(2)"],
                    "timeout_seconds": 1,
                },
                Path(directory),
            )

        self.assertEqual(result["verdict"], "FAIL")
        self.assertTrue(result["evidence"]["timed_out"])


class FileVerifierTests(unittest.TestCase):
    def test_existing_static_file_is_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "artifact.txt").write_text("evidence", encoding="utf-8")
            result = verify_file(
                {
                    "id": "artifact",
                    "type": "file",
                    "path": "artifact.txt",
                    "freshness": "none",
                    "min_bytes": 1,
                },
                root,
                time.time_ns(),
            )

        self.assertEqual(result["verdict"], "PASS")
        self.assertEqual(result["evidence"]["size_bytes"], 8)
        self.assertEqual(len(result["evidence"]["sha256"]), 64)

    def test_missing_file_is_fail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = verify_file(
                {
                    "id": "artifact",
                    "type": "file",
                    "path": "missing.txt",
                    "freshness": "run",
                },
                Path(directory),
                time.time_ns(),
            )

        self.assertEqual(result["verdict"], "FAIL")

    def test_stale_file_is_unproven(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.txt"
            artifact.write_text("old evidence", encoding="utf-8")
            old_time = time.time() - 60
            os.utime(artifact, (old_time, old_time))
            result = verify_file(
                {
                    "id": "artifact",
                    "type": "file",
                    "path": "artifact.txt",
                    "freshness": "run",
                },
                root,
                time.time_ns(),
            )

        self.assertEqual(result["verdict"], "UNPROVEN")

    def test_too_small_file_is_fail_before_freshness(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifact = root / "artifact.txt"
            artifact.write_bytes(b"")
            old_time = time.time() - 60
            os.utime(artifact, (old_time, old_time))
            result = verify_file(
                {
                    "id": "artifact",
                    "type": "file",
                    "path": "artifact.txt",
                    "freshness": "run",
                    "min_bytes": 1,
                },
                root,
                time.time_ns(),
            )

        self.assertEqual(result["verdict"], "FAIL")
        self.assertIn("minimum", result["reason"])

    def test_symlink_escape_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            root.mkdir()
            outside = base / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "artifact.txt").symlink_to(outside)
            result = verify_file(
                {
                    "id": "artifact",
                    "type": "file",
                    "path": "artifact.txt",
                    "freshness": "none",
                },
                root,
                time.time_ns(),
            )

        self.assertEqual(result["verdict"], "BLOCKED")
        self.assertIn("escapes", result["reason"])
