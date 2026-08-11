import json
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
