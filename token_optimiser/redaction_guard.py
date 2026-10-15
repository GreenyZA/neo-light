"""Local redaction guard for Monica's T1 GPU workloads.

The router decides *to* run redaction locally (T1). This module makes sure
the *output* of that redaction is actually safe before it is trusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List


REDACTION_PLACEHOLDER = "[REDACTED]"

REDACTION_SYSTEM_PROMPT = """You are a strict redaction engine. Your only job is to remove sensitive identifiers from the supplied text.

Rules:
- Replace every sensitive identifier with the literal token [REDACTED].
- Sensitive identifiers include: names, email addresses, phone/mobile/telephone numbers, identity/ID/passport numbers, bank/card/account numbers, CVV/PAN, GPS coordinates, addresses, and any identifier that could identify a person.
- Do not repeat, quote, summarise, or partially disclose any original value.
- Do not add explanations, context, warnings, or commentary.
- Return only the transformed text.
- If there is nothing to redact, return the original text unchanged.
"""


_PATTERNS: Dict[str, re.Pattern] = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "phone": re.compile(r"(?:(?:\+|00)\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?){2,}\d{3,}"),
    "south_african_id": re.compile(r"\b\d{13}\b"),
    "generic_long_number": re.compile(r"\b\d{8,16}\b"),
    "credit_card": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "password_hint": re.compile(r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+"),
    "account_label": re.compile(r"(?i)(account|acct)[\s#:-]*\d{4,}"),
    "gps": re.compile(r"-?\d{1,3}\.\d{5,}"),
}


@dataclass
class RedactionResult:
    safe: bool
    leaks: List[str]
    placeholder_present: bool
    reason: str


def build_redaction_prompt(text: str) -> str:
    """Build the user-side prompt for a redaction task."""
    return (
        REDACTION_SYSTEM_PROMPT
        + "\n\nRedact the following text:\n" + text
    )


def find_pii_leaks(text: str) -> List[str]:
    """Return the names of PII pattern classes still present in *text*."""
    hits = []
    for name, pattern in _PATTERNS.items():
        if pattern.search(text or ""):
            hits.append(name)
    return hits


def _digit_runs(text: str, min_len: int = 4) -> set:
    """Return digit runs of at least *min_len* found in *text*."""
    return {m.group(0) for m in re.finditer(r"\d{" + str(min_len) + r",}", text or "")}


_SENSITIVE_TOKEN_STOPWORDS = {
    "email", "phone", "mobile", "telephone", "contact", "address", "account",
    "identity", "passport", "customer", "client", "user", "name", "note",
}


def _sensitive_tokens(text: str) -> set:
    """Return likely sensitive word tokens from *text* (capitalized words >= 4 chars)."""
    tokens = set()
    for token in re.findall(r"[A-Za-z0-9_-]{4,}", text or ""):
        if token.isupper() or (token and token[0].isupper()):
            low = token.lower()
            if low not in _SENSITIVE_TOKEN_STOPWORDS:
                tokens.add(low)
    return tokens


def validate_redaction(original: str, candidate: str) -> RedactionResult:
    """Validate that *candidate* does not leak PII from *original*."""
    original = original or ""
    candidate = candidate or ""
    leaks = find_pii_leaks(candidate)
    placeholder_present = REDACTION_PLACEHOLDER in candidate

    # Catch partially preserved identifiers that regex patterns miss, e.g.
    # "+27 [REDACTED]0000" or "account [REDACTED]12".
    leaked_runs = _digit_runs(original) & _digit_runs(candidate)
    if leaked_runs:
        leaks = leaks + ["numeric_fragment"]
    original_tokens = _sensitive_tokens(original)
    candidate_tokens = _sensitive_tokens(candidate)
    preserved_tokens = original_tokens & candidate_tokens
    if preserved_tokens:
        leaks = leaks + ["original_token"]

    if not candidate.strip():
        return RedactionResult(False, leaks, False, "empty output")

    if candidate.strip() == original.strip():
        if find_pii_leaks(original):
            return RedactionResult(False, leaks or ["unchanged"], placeholder_present,
                                 "output is identical to PII-containing input")
        return RedactionResult(True, [], placeholder_present, "no PII detected in input")

    leaks = list(dict.fromkeys(leaks))
    if leaks:
        return RedactionResult(False, leaks, placeholder_present,
                             "PII patterns remain in candidate output")

    # De-duplicate leak reasons while preserving order.
    leaks = list(dict.fromkeys(leaks))
    return RedactionResult(True, [], placeholder_present, "candidate contains no detectable PII")


def redaction_confidence(result: RedactionResult) -> float:
    """Map a validation result to a simple 0.0-1.0 confidence score."""
    if not result.safe:
        return 0.2
    return 1.0 if result.placeholder_present else 0.7