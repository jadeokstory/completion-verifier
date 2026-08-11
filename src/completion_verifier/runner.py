import time
from typing import Any

from .contract import Contract
from .git_state import observe_git_state
from .timeutil import isoformat, utc_now
from .verdict import Verdict, overall_verdict
from .verifiers import verify_command, verify_file


def run_contract(contract: Contract) -> dict[str, Any]:
    started = utc_now()
    started_ns = time.time_ns()
    git_before = observe_git_state(contract.root)
    results: list[dict[str, Any]] = []

    for check in contract.checks:
        if check["type"] == "command":
            result = verify_command(check, contract.root)
        elif check["type"] == "file":
            result = verify_file(check, contract.root, started_ns)
        else:  # The schema makes this unreachable.
            raise AssertionError(f"unsupported verifier type: {check['type']}")
        results.append(result)

    finished = utc_now()
    git_after = observe_git_state(contract.root)
    verdict = overall_verdict(Verdict(result["verdict"]) for result in results)
    redaction_applied = any(
        result["evidence"].get("redaction_applied", False) for result in results
    )
    return {
        "schema_version": 1,
        "gate": contract.gate,
        "verdict": verdict.value,
        "started_at": isoformat(started),
        "finished_at": isoformat(finished),
        "working_directory": str(contract.root),
        "contract": str(contract.path),
        "git": {
            "before": git_before,
            "after": git_after,
            "changed_during_run": git_before != git_after,
        },
        "redaction_applied": redaction_applied,
        "checks": results,
    }
