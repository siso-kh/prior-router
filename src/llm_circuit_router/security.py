"""Keep provider credentials out of logs, error output, and rendered settings.

Two mechanisms are provided:

* :func:`find_secrets` locates credential-shaped substrings, which lets tests
  audit version-controlled files for accidentally committed keys.
* :func:`redact_secrets` masks those substrings — plus any explicitly supplied
  value — before a message is written to a log or printed.
"""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

REDACTED = "***REDACTED***"

# Anything shorter than this is treated as a placeholder, not a credential.
_MIN_SECRET_LENGTH = 8

# Real provider keys are far longer than this, and are opaque (no ``.``), so a
# long, dot-free value keeps the assignment pattern from firing on ordinary
# source such as ``api_key=settings.OPENROUTER_API_KEY``.
_MIN_ASSIGNMENT_VALUE_LENGTH = 20

# Values that are placeholders rather than real credentials.
_NON_SECRET_VALUES = frozenset({"", "***", "none", "null", REDACTED.lower()})

# Credential prefixes used by the providers this project talks to.
_PREFIX_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-(?:or-)?[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bnar-[A-Za-z0-9_\-]{8,}", re.IGNORECASE),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{8,}"),
)

# ``name = value`` / ``name: value`` style assignments.
_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)(?P<name>\b(?:api[_-]?key|apikey|token|secret|password)\b)"
    r"(?P<separator>[\"']?\s*[:=]\s*)"
    r"(?P<quote>[\"']?)"
    rf"(?P<value>[A-Za-z0-9_\-]{{{_MIN_ASSIGNMENT_VALUE_LENGTH},}})"
)


def find_secrets(text: str) -> List[str]:
    """Return every credential-shaped substring found in ``text``."""
    found: List[str] = []
    for pattern in _PREFIX_PATTERNS:
        found.extend(match.group(0) for match in pattern.finditer(text))
    found.extend(match.group("value") for match in _ASSIGNMENT_PATTERN.finditer(text))
    return found


def redact_secrets(text: str, extra: Iterable[Optional[str]] = ()) -> str:
    """Return ``text`` with credential-shaped substrings masked.

    Args:
        text: The message to sanitise.
        extra: Values known to be sensitive (for example the active model's
            credential), masked even when they match no known prefix.
    """
    redacted = str(text)

    for value in extra:
        if _looks_like_a_secret(value):
            redacted = redacted.replace(value, REDACTED)

    for pattern in _PREFIX_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)

    return _ASSIGNMENT_PATTERN.sub(_mask_assignment, redacted)


def _mask_assignment(match: re.Match[str]) -> str:
    """Keep the field name and punctuation, mask only the value."""
    return (
        f"{match.group('name')}{match.group('separator')}"
        f"{match.group('quote')}{REDACTED}"
    )


def _looks_like_a_secret(value: Optional[str]) -> bool:
    """Whether ``value`` is plausibly a real credential worth masking."""
    return (
        isinstance(value, str)
        and len(value) >= _MIN_SECRET_LENGTH
        and value.lower() not in _NON_SECRET_VALUES
    )
