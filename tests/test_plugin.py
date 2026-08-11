import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_SCRIPT = Path(__file__).parent.parent / "scripts" / "proofgate_plugin.py"


class ProofGatePluginTests(unittest.TestCase):
    def test_install_runtime_hook_and_uninstall(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime = root / "runtime"
            hooks = root / "hooks.json"
            state = root / "state"
            project = root / "project"
            project.mkdir()
            environment = dict(os.environ)
            environment["COMPLETION_VERIFIER_STATE_DIR"] = str(state)

            installed = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_SCRIPT),
                    "install",
                    "--hooks-file",
                    str(hooks),
                    "--runtime-dir",
                    str(runtime),
                ],
                capture_output=True,
                check=False,
                text=True,
                env=environment,
            )
            self.assertEqual(installed.returncode, 0, installed.stderr)
            self.assertTrue((runtime / "proofgate_plugin.py").is_file())
            self.assertTrue(
                (runtime / "completion_verifier" / "claim-evaluation.schema.json").is_file()
            )
            metadata = json.loads(
                (runtime / "installation.json").read_text(encoding="utf-8")
            )
            self.assertIn(str(runtime / "proofgate_plugin.py"), metadata["hook_command"])
            self.assertEqual(hooks.stat().st_mode & 0o777, 0o600)

            status = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_SCRIPT),
                    "status",
                    "--hooks-file",
                    str(hooks),
                    "--runtime-dir",
                    str(runtime),
                ],
                capture_output=True,
                check=False,
                text=True,
                env=environment,
            )
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn("ProofGate hooks: installed", status.stdout)

            post_event = {
                "session_id": "plugin-session",
                "turn_id": "plugin-turn",
                "cwd": str(project),
                "hook_event_name": "PostToolUse",
                "tool_name": "Bash",
                "tool_use_id": "plugin-tool",
                "tool_input": {"command": "python -m unittest"},
                "tool_response": {"exit_code": 0, "output": "45 tests passed"},
            }
            hook_run = subprocess.run(
                [sys.executable, str(runtime / "proofgate_plugin.py"), "hook"],
                input=json.dumps(post_event),
                capture_output=True,
                check=False,
                text=True,
                env=environment,
            )
            self.assertEqual(hook_run.returncode, 0, hook_run.stderr)
            stored_events = list(state.rglob("events.jsonl"))
            self.assertEqual(len(stored_events), 1)
            self.assertIn("plugin-tool", stored_events[0].read_text(encoding="utf-8"))

            uninstalled = subprocess.run(
                [
                    sys.executable,
                    str(PLUGIN_SCRIPT),
                    "uninstall",
                    "--hooks-file",
                    str(hooks),
                    "--runtime-dir",
                    str(runtime),
                ],
                capture_output=True,
                check=False,
                text=True,
                env=environment,
            )
            self.assertEqual(uninstalled.returncode, 0, uninstalled.stderr)
            hook_document = json.loads(hooks.read_text(encoding="utf-8"))
            self.assertNotIn("PostToolUse", hook_document["hooks"])
            self.assertNotIn("Stop", hook_document["hooks"])


if __name__ == "__main__":
    unittest.main()
