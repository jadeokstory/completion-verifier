import re
from dataclasses import dataclass


_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{8,}\b"),
    re.compile(
        r"(?i)\b(api[_-]?key|access[_-]?token|token|password|secret)"
        r"(\s*[:=]\s*)([^\s,;]+)"
    ),
    re.compile(r"(?i)(https?://[^:/\s]+:)([^@/\s]+)(@)"),
)


@dataclass(frozen=True)
class RedactedText:
    text: str
    applied: bool


def redact(text: str) -> RedactedText:
    applied = False
    result = text

    def replace_all(match: re.Match[str]) -> str:
        nonlocal applied
        applied = True
        if match.lastindex == 3:
            if match.re.pattern.startswith("(?i)(https?"):
                return f"{match.group(1)}[REDACTED]{match.group(3)}"
            return f"{match.group(1)}{match.group(2)}[REDACTED]"
        return "[REDACTED]"

    for pattern in _PATTERNS:
        result = pattern.sub(replace_all, result)
    return RedactedText(text=result, applied=applied)
