"""Deterministic safety net for AI writing: the model must never invent metrics.

Any number in AI output that doesn't appear in the user's own text is replaced with a
placeholder ([X], [X%], [$X]) the user must fill in. Placeholders are reported so the UI can
flag them.
"""

import re
from dataclasses import dataclass

# A standalone number, optionally with currency, thousands separators, decimals and a unit.
# Digits inside words (S3, EC2, p95, ES6, OAuth2) are tech names, not metrics.
_NUMBER = re.compile(
    r"(?<![A-Za-z0-9.])"
    r"(?P<currency>[$€£¥])?"
    r"(?P<core>\d{1,3}(?:,\d{3})+|\d+)(?P<decimal>\.\d+)?"
    r"(?P<unit>\s?%|\+|x\b|k\b|K\b|m\b|M\b|bn\b|B\b)?"
    r"(?![A-Za-z0-9])",
)
_PLACEHOLDER = re.compile(r"\[[^\[\]\n]{1,24}\]")


def _key(match: re.Match[str]) -> str:
    return match["core"].replace(",", "") + (match["decimal"] or "")


def number_keys(*texts: str) -> set[str]:
    """Numeric values present in the user's own text ("2,000" and "2000" are the same)."""
    return {_key(m) for text in texts for m in _NUMBER.finditer(text or "")}


def placeholders(text: str) -> list[str]:
    return list(dict.fromkeys(_PLACEHOLDER.findall(text)))


@dataclass(frozen=True)
class Guarded:
    text: str
    replaced: list[str]  # invented numbers that were swapped for placeholders
    placeholders: list[str]


def guard_numbers(text: str, allowed: set[str]) -> Guarded:
    replaced: list[str] = []

    def swap(match: re.Match[str]) -> str:
        if _key(match) in allowed:
            return match[0]
        replaced.append(match[0])
        unit = (match["unit"] or "").strip()
        if match["currency"]:
            return f"[{match['currency']}X]"
        if unit == "%":
            return "[X%]"
        if unit.lower() == "x":
            return "[X]x"
        return "[X]"

    cleaned = _NUMBER.sub(swap, text)
    return Guarded(text=cleaned, replaced=replaced, placeholders=placeholders(cleaned))
