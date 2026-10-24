"""Local redaction guard for Monica's T1 GPU workloads.

The router decides *to* run redaction locally (T1). This module makes sure
the *output* of that redaction is actually safe before it is trusted.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List


_SENSITIVE_CAPS_LABELS = {
    "from", "to", "subject", "body", "dear", "regards", "call", "customer",
    "alternate", "meeting", "company", "postal", "code", "client", "record",
    "payment", "location", "account", "invoice", "centre", "note", "id",
    "cvv", "gps", "email", "phone", "address", "name", "please", "hi",
}

REDACTION_PLACEHOLDER = "[REDACTED]"

REDACTION_SYSTEM_PROMPT = """You are a strict redaction engine. Your only job is to remove sensitive identifiers from the supplied text.

Rules:
- Replace every sensitive identifier with the literal token [REDACTED].
- Sensitive identifiers include: names, email addresses, phone/mobile/telephone numbers, identity/ID/passport numbers, bank/card/account numbers, CVV/PAN, GPS coordinates, addresses, company/organisation names, and any identifier that could identify a person.
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
    "password_hint": re.compile(r"(?i)(password|passwd|pwd)\s*(?::|=|is|was)\s*\S+"),
    "account_label": re.compile(r"(?i)(account|acct)[\s#:-]*\d{4,}"),
    "gps": re.compile(r"-?\d{1,3}\.\d{5,}"),
    "cvv": re.compile(r"(?i)\b(?:cvv|cvc)\b\s*[:#-]?\s*\d{3,4}\b"),
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


def _digit_runs(text: str, min_len: int = 6) -> set:
    """Return digit runs of at least *min_len* found in *text*."""
    return {m.group(0) for m in re.finditer(r"\d{" + str(min_len) + r",}", text or "")}


_SENSITIVE_TOKEN_STOPWORDS = {
    # common English / structural words that legitimately survive redaction
    "email", "phone", "mobile", "telephone", "contact", "address", "account",
    "office",
    "identity", "passport", "customer", "client", "user", "name", "note",
    "please", "redact", "patient", "diagnosis", "info", "login", "subject",
    "from", "to", "event", "meeting", "speaker", "transcript", "password",
    "salary", "employee", "record", "attachment", "text", "export", "row",
    "document", "title", "author", "created", "tags", "summary", "revenue",
    "given", "anonymized", "postal", "profession", "assess", "risk", "level",
    "output", "preprocess", "csv", "indexing", "metadata", "index", "dob",
    "card", "gps", "ip", "auth", "token", "birthday", "invoice", "query",
    "refund", "charged", "twice", "hello", "long", "street", "cape", "town",
    "bank", "number", "age", "engineer", "internal", "finance", "revenue",
    "anonymized", "record", "hypertension", "info", "login", "ok",
    "the", "and", "for", "with", "this", "that", "are", "was", "were",
    "has", "have", "had", "not", "but", "all", "any", "can", "will",
    "just", "more", "also", "into", "than", "then", "now", "only",
    "other", "some", "such", "what", "when", "which", "who", "how",
    "their", "there", "these", "those", "your", "you", "its", "our",
}


def _sensitive_tokens(text: str) -> set:
    """Return likely sensitive word tokens from *text* (capitalized words >= 4 chars)."""
    tokens = set()
    for token in re.findall(r"[A-Za-z0-9_-]{4,}", text or ""):
        if token.isupper() or (token and token[0].isupper()):
            low = token.lower()
            if low not in _SENSITIVE_TOKEN_STOPWORDS and low not in _SENSITIVE_CAPS_LABELS:
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


def deterministic_redact(text: str) -> str:
    """Deterministically replace all detectable PII with the redaction placeholder."""
    result = text or ""
    for _name, pattern in _PATTERNS.items():
        result = pattern.sub(REDACTION_PLACEHOLDER, result)
    # Redact capitalised name/company/address tokens that survived regex masking.
    def _repl_cap(match: re.Match) -> str:
        token = match.group(0)
        if token.lower() in _SENSITIVE_TOKEN_STOPWORDS or token.lower() in _SENSITIVE_CAPS_LABELS:
            return token
        if token.lower() == "redacted":
            return token
        return REDACTION_PLACEHOLDER
    result = re.sub(r"\b[A-Z][A-Za-z'-]{2,}\b", _repl_cap, result)
    return result


def safe_redact_output(original: str, candidate: str) -> str:
    """Return a trusted redaction, falling back to deterministic masking if needed."""
    candidate = candidate or ""
    validation = validate_redaction(original or "", candidate)
    if validation.safe:
        return candidate
    # First try masking whatever leaked in the model output.
    masked_candidate = deterministic_redact(candidate)
    if validate_redaction(original or "", masked_candidate).safe:
        return masked_candidate
    # Last resort: redact the original deterministically.
    return deterministic_redact(original or "")
