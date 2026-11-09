"""Checks every generated text must pass before anyone sees it.

1. Compliance language - no promissory or exaggerated claims (guarantees, "risk-free",
   "will outperform"...). Inspired by the content standards in FINRA Rule 2210 for
   communications about investment products; a real deployment would also route
   advisor-facing material through compliance review.
2. Number grounding - every dollar amount and percentage in the text must match a number in
   the facts the model was given (catches hallucinated figures).
3. Required footer - internal-use disclaimer present.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

BANNED = [
    (r"\bguarantee[sd]?\b", "guarantee"),
    (r"\brisk[- ]free\b", "risk-free"),
    (r"\bno[- ]risk\b", "no risk"),
    (r"\bcan(?:'|no)?t (?:lose|go wrong)\b", "can't lose"),
    (r"\bwill (?:outperform|beat|double|deliver|return|grow)\b", "performance prediction"),
    (r"\bpromis(?:e|es|ed|ing)\b", "promise"),
    (r"\bsure (?:thing|bet|winner)\b", "sure thing"),
    (r"\bonly goes up\b", "only goes up"),
    (r"\bprotect(?:s|ed)? (?:clients |you )?from (?:all )?loss(?:es)?\b", "loss protection claim"),
    (r"\bbest[- ]performing fund (?:ever|in the industry)\b", "superlative claim"),
]
FOOTER = "For internal use only. Not for distribution to clients or the public."

NUM_RE = re.compile(r"(?<![\w.])([-+]?\$?\d[\d,]*(?:\.\d+)?)\s*(%|[MBK]\b|bps\b|x\b)?", re.IGNORECASE)


@dataclass
class GuardrailResult:
    ok: bool
    issues: list = field(default_factory=list)


def _value(token: str, suffix: str | None) -> tuple[float, str]:
    t = token.replace("$", "").replace(",", "").replace("+", "")
    v = float(t)
    s = (suffix or "").lower()
    if s == "m":
        return v * 1e6, "usd"
    if s == "b":
        return v * 1e9, "usd"
    if s == "k":
        return v * 1e3, "usd"
    if s == "%":
        return v / 100, "pct"
    if s == "bps":
        return v, "bps"
    if s == "x":
        return v, "x"
    return v, "usd" if "$" in token else "plain"


def numbers_in(text: str) -> list[tuple[str, float, str]]:
    out = []
    for m in NUM_RE.finditer(text):
        tok, suf = m.group(1), m.group(2)
        try:
            v, kind = _value(tok, suf)
        except ValueError:
            continue
        out.append((m.group(0).strip(), v, kind))
    return out


def allowed_numbers(facts) -> list[float]:
    vals = []

    def walk(x):
        if isinstance(x, bool):
            return
        if isinstance(x, (int, float)):
            vals.append(float(x))
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, (list, tuple)):
            for v in x:
                walk(v)
        elif isinstance(x, str):
            for _, v, _k in numbers_in(x):
                vals.append(v)
    walk(facts)
    return vals


def _supported(v: float, kind: str, allowed: list[float]) -> bool:
    if kind == "plain" and (abs(v) <= 31 or 1990 <= abs(v) <= 2100):
        return True                                  # counts, days, months, years
    for a in allowed:
        if a == 0:
            if abs(v) < 1e-9:
                return True
            continue
        if kind == "pct" and abs(v - a) <= max(0.0051, abs(a) * 0.02):
            return True                              # rounded percentages
        if abs(v - a) / abs(a) <= 0.051:
            return True                              # $1.2M vs 1,234,567
        if kind == "plain" and abs(v - a * 100) <= 0.51:
            return True                              # "62" written for 0.62
    return False


# Negated forms are the standard disclaimer, not a claim ("past performance does not guarantee...").
NEGATED = re.compile(r"\b(?:does not|doesn't|do not|don't|cannot|can't|is not|are not|not|no)\s+"
                     r"(?:a\s+)?guarantee[sd]?\b|\bnot guaranteed\b")


def review(text: str, facts, require_footer: bool = True) -> GuardrailResult:
    issues = []
    low = NEGATED.sub(" ", text.lower())
    for pattern, label in BANNED:
        if re.search(pattern, low):
            issues.append(f"compliance: {label}")
    allowed = allowed_numbers(facts)
    for raw, v, kind in numbers_in(text):
        if not _supported(abs(v), kind, [abs(a) for a in allowed]):
            issues.append(f"ungrounded number: {raw}")
    if require_footer and FOOTER.lower() not in low:
        issues.append("missing internal-use footer")
    return GuardrailResult(not issues, issues)
