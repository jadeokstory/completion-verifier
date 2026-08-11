import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema
import yaml


DEFAULT_CONFIG_NAME = "completion-verifier.yml"


class ContractError(ValueError):
    pass


@dataclass(frozen=True)
class Contract:
    path: Path
    root: Path
    data: dict[str, Any]

    @property
    def gate(self) -> str:
        return self.data["gate"]

    @property
    def checks(self) -> list[dict[str, Any]]:
        return self.data["checks"]


def load_schema() -> dict[str, Any]:
    schema_file = resources.files("completion_verifier").joinpath(
        "completion-verifier.schema.json"
    )
    return json.loads(schema_file.read_text(encoding="utf-8"))


def validate_contract_data(data: object) -> dict[str, Any]:
    validator = jsonschema.Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(data), key=lambda error: list(error.path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ContractError(f"invalid contract at {location}: {error.message}")

    assert isinstance(data, dict)
    check_ids = [check["id"] for check in data["checks"]]
    if len(check_ids) != len(set(check_ids)):
        raise ContractError("invalid contract: check ids must be unique")
    return data


def load_contract(path: Path) -> Contract:
    resolved_path = path.resolve()
    try:
        raw = resolved_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ContractError(f"cannot read contract {path}: {error.strerror or error}") from error

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as error:
        raise ContractError(f"cannot parse contract {path}: {error}") from error

    validated = validate_contract_data(data)
    return Contract(path=resolved_path, root=resolved_path.parent, data=validated)
