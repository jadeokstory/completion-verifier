import re
from dataclasses import dataclass


_URL_CREDENTIAL_PATTERN = re.compile(
    r"(?i)([a-z][a-z0-9+.-]*://[^:/\s]+:)([^@/\s]+)(@)"
)
_AUTHORIZATION_PATTERN = re.compile(
    r"(?i)\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{4,}"
)
_PRIVATE_KEY_PATTERN = re.compile(
    r"-----BEGIN ((?:[A-Z0-9]+ )*PRIVATE KEY)-----.*?"
    r"-----END \1-----",
    re.DOTALL,
)
_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)("
    r"[\"']?(?:"
    r"api[_-]?key|"
    r"aws[_-]?(?:access[_-]?key[_-]?id|secret[_-]?access[_-]?key|session[_-]?token)|"
    r"(?:database|db)[_-]?url|connection[_-]?string|"
    r"access[_-]?token|refresh[_-]?token|client[_-]?secret|"
    r"private[_-]?key|token|password|passwd|secret"
    r")[\"']?\s*[:=]\s*)"
    r"(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[^\s,;]+)"
)
_PATTERNS = (
    _PRIVATE_KEY_PATTERN,
    _AUTHORIZATION_PATTERN,
    re.compile(r"\b(?:sk|ghp|github_pat|xox[baprs])[-_][A-Za-z0-9_-]{8,}\b"),
    _SECRET_ASSIGNMENT_PATTERN,
    _URL_CREDENTIAL_PATTERN,
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
        if match.re is _URL_CREDENTIAL_PATTERN:
            return f"{match.group(1)}[REDACTED]{match.group(3)}"
        if match.re is _SECRET_ASSIGNMENT_PATTERN:
            return f"{match.group(1)}[REDACTED]"
        return "[REDACTED]"

    for pattern in _PATTERNS:
        result = pattern.sub(replace_all, result)
    return RedactedText(text=result, applied=applied)
