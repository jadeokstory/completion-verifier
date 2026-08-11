import json
import unittest
from pathlib import Path

import jsonschema
import yaml

from completion_verifier.contract import ContractError, validate_contract_data


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads(
    (ROOT / "schemas" / "completion-verifier.schema.json").read_text()
)


def validate_contract(contract: object) -> None:
    jsonschema.Draft202012Validator(SCHEMA).validate(contract)
    check_ids = [check["id"] for check in contract["checks"]]
    if len(check_ids) != len(set(check_ids)):
        raise ValueError("check ids must be unique")


class ContractSchemaTests(unittest.TestCase):
    def test_published_and_packaged_schemas_match(self) -> None:
        self.assertEqual(
            (ROOT / "schemas" / "completion-verifier.schema.json").read_bytes(),
            (
                ROOT
                / "src"
                / "completion_verifier"
                / "completion-verifier.schema.json"
            ).read_bytes(),
        )

    def test_minimal_example_is_valid(self) -> None:
        contract = yaml.safe_load(
            (ROOT / "examples" / "completion-verifier.minimal.yml").read_text()
        )

        validate_contract(contract)

    def test_static_file_requires_explicit_freshness_none(self) -> None:
        validate_contract(
            {
                "version": 1,
                "gate": "source-present",
                "checks": [
                    {
                        "id": "license",
                        "type": "file",
                        "path": "LICENSE",
                        "freshness": "none",
                    }
                ],
            }
        )

    def test_unknown_field_is_rejected(self) -> None:
        contract = {
            "version": 1,
            "gate": "tests",
            "checks": [
                {
                    "id": "tests",
                    "type": "command",
                    "command": ["pytest"],
                    "timeout_seconds": 120,
                    "optional": True,
                }
            ],
        }

        with self.assertRaises(jsonschema.ValidationError):
            validate_contract(contract)

    def test_shell_string_is_rejected(self) -> None:
        contract = {
            "version": 1,
            "gate": "tests",
            "checks": [
                {
                    "id": "tests",
                    "type": "command",
                    "command": "pytest && echo done",
                    "timeout_seconds": 120,
                }
            ],
        }

        with self.assertRaises(jsonschema.ValidationError):
            validate_contract(contract)

    def test_file_without_freshness_is_rejected(self) -> None:
        contract = {
            "version": 1,
            "gate": "artifact",
            "checks": [
                {
                    "id": "artifact",
                    "type": "file",
                    "path": "dist/app.tar.gz",
                }
            ],
        }

        with self.assertRaises(jsonschema.ValidationError):
            validate_contract(contract)

    def test_absolute_and_parent_paths_are_rejected(self) -> None:
        for path in (
            "/tmp/result",
            "../result",
            "dist/../../result",
            "C:\\result",
            "\\\\server\\share\\result",
        ):
            with self.subTest(path=path):
                contract = {
                    "version": 1,
                    "gate": "artifact",
                    "checks": [
                        {
                            "id": "artifact",
                            "type": "file",
                            "path": path,
                            "freshness": "run",
                        }
                    ],
                }

                with self.assertRaises(jsonschema.ValidationError):
                    validate_contract(contract)

    def test_duplicate_check_ids_are_rejected_semantically(self) -> None:
        contract = {
            "version": 1,
            "gate": "release-ready",
            "checks": [
                {
                    "id": "tests",
                    "type": "command",
                    "command": ["pytest"],
                    "timeout_seconds": 120,
                },
                {
                    "id": "tests",
                    "type": "file",
                    "path": "result.txt",
                    "freshness": "run",
                },
            ],
        }

        with self.assertRaisesRegex(ValueError, "check ids must be unique"):
            validate_contract(contract)

        with self.assertRaisesRegex(ContractError, "check ids must be unique"):
            validate_contract_data(contract)


if __name__ == "__main__":
    unittest.main()
