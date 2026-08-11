from enum import Enum
from typing import Iterable


class Verdict(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNPROVEN = "UNPROVEN"
    BLOCKED = "BLOCKED"


_PRECEDENCE = {
    Verdict.PASS: 0,
    Verdict.UNPROVEN: 1,
    Verdict.BLOCKED: 2,
    Verdict.FAIL: 3,
}


def overall_verdict(verdicts: Iterable[Verdict]) -> Verdict:
    values = list(verdicts)
    if not values:
        raise ValueError("at least one verdict is required")
    return max(values, key=_PRECEDENCE.__getitem__)
