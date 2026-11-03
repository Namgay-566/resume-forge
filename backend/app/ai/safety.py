"""Deterministic prompt-injection screening for untrusted text we hand to the AI.

The first line of defence is structural: untrusted text is wrapped in data tags that it can't
close (see prompts.defang), and every system prompt says it's data. This is the second line:
where the AI's judgement decides an outcome (repo verification), text that tries to address
the reviewer is flagged and blocks automatic verification, whatever the model then says.
"""

import re

_WHO = r"(ai|llm|reviewer|grader|evaluator|model|assessor)"
_THING = r"(repo(sitory)?|project|proof|candidate|submission|code)"

# Aimed at whoever grades the repo. Legitimate code has no reason to say this anywhere.
_REVIEWER = [
    rf"\b(note|message|instructions?|hint)\s+(to|for)\s+(the\s+|any\s+)?{_WHO}s?\b",
    rf"\b(dear|hey|attention|hello)\s+{_WHO}\b",
    rf"\b(approve|verify|pass|accept)\s+(this|the)\s+{_THING}\b",
    r"\b(give|assign|award|rate)\b[^.\n]{0,40}\b(score|rating|grade)\b[^.\n]{0,20}"
    r"\b(100|10/10|maximum|max|highest|perfect)\b",
]
# Generic jailbreak phrasing. Only checked in prose (README, description, commits): source
# code of LLM apps legitimately contains prompts like "You are a helpful assistant".
_GENERIC = [
    r"\b(ignore|disregard|forget|override)\b[^.\n]{0,40}\b(previous|prior|above|earlier|all)\b"
    r"[^.\n]{0,20}\b(instructions?|prompts?|rules|guidelines)\b",
    r"\b(new|updated|real|actual)\s+instructions\b",
    r"</?\s*(system|assistant|instructions?)\s*>",
]


def _compile(patterns: list[str]) -> re.Pattern[str]:
    return re.compile("|".join(f"(?:{p})" for p in patterns), re.IGNORECASE)


_TARGETED = _compile(_REVIEWER)
_ANY = _compile(_REVIEWER + _GENERIC)


def find_injection(prose: dict[str, str | None], code: dict[str, str] | None = None) -> list[str]:
    """Names of the sources containing text aimed at the AI reviewer.

    `prose` (README, description, commit messages) is checked for all patterns; `code`
    (source and config files) only for reviewer-directed ones.
    """
    hits = [name for name, text in prose.items() if text and _ANY.search(text)]
    return hits + [name for name, text in (code or {}).items() if text and _TARGETED.search(text)]
