import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from completion_verifier.contract import load_contract
from completion_verifier.runner import run_contract


def _write_contract(root: Path, checks: list[dict[str, object]]) -> Path:
    path = root / "completion-verifier.yml"
    path.write_text(
        json.dumps({"version": 1, "gate": "release-ready", "checks": checks}),
        encoding="utf-8",
    )
    return path


class RunnerTests(unittest.TestCase):
    def test_dirty_git_state_detects_new_file_created_during_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract_path = _write_contract(
                root,
                [
                    {
                        "id": "create-file",
                        "type": "command",
                        "command": [
                            sys.executable,
                            "-c",
                            "from pathlib import Path; Path('created.txt').write_text('new')",
                        ],
                        "timeout_seconds": 5,
                    }
                ],
            )
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(
                ["git", "-C", str(root), "config", "user.name", "Test User"],
                check=True,
            )
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(root),
                    "config",
                    "user.email",
                    "test@example.invalid",
                ],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(root), "add", contract_path.name], check=True
            )
            subprocess.run(
                ["git", "-C", str(root), "commit", "-qm", "initial"], check=True
            )
            (root / "already-dirty.txt").write_text("existing", encoding="utf-8")

            receipt = run_contract(load_contract(contract_path))

        self.assertTrue(receipt["git"]["before"]["dirty"])
        self.assertTrue(receipt["git"]["after"]["dirty"])
        self.assertNotEqual(
            receipt["git"]["before"]["status_sha256"],
            receipt["git"]["after"]["status_sha256"],
        )
        self.assertTrue(receipt["git"]["changed_during_run"])

    def test_command_can_create_fresh_file_for_later_check(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = load_contract(
                _write_contract(
                    root,
                    [
                        {
                            "id": "build",
                            "type": "command",
                            "command": [
                                sys.executable,
                                "-c",
                                "from pathlib import Path; Path('artifact.txt').write_text('ok')",
                            ],
                            "timeout_seconds": 5,
                        },
                        {
                            "id": "artifact",
                            "type": "file",
                            "path": "artifact.txt",
                            "freshness": "run",
                            "min_bytes": 1,
                        },
                    ],
                )
            )
            receipt = run_contract(contract)

        self.assertEqual(receipt["verdict"], "PASS")
        self.assertEqual(
            [result["verdict"] for result in receipt["checks"]], ["PASS", "PASS"]
        )
        self.assertIn("before", receipt["git"])
        self.assertIn("after", receipt["git"])

    def test_fail_takes_precedence_over_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            contract = load_contract(
                _write_contract(
                    root,
                    [
                        {
                            "id": "failure",
                            "type": "command",
                            "command": [sys.executable, "-c", "raise SystemExit(1)"],
                            "timeout_seconds": 5,
                        },
                        {
                            "id": "blocked",
                            "type": "command",
                            "command": ["completion-verifier-command-that-does-not-exist"],
                            "timeout_seconds": 5,
                        },
                    ],
                )
            )
            receipt = run_contract(contract)

        self.assertEqual(receipt["verdict"], "FAIL")
