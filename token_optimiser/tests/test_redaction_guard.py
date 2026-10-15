"""Tests for the local redaction guard."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from token_optimiser.redaction_guard import (
    build_redaction_prompt,
    find_pii_leaks,
    validate_redaction,
    REDACTION_PLACEHOLDER,
    deterministic_redact,
    safe_redact_output,
)


def test_find_leaks_detects_known_pii():
    text = "Johann Venter, ID 9001015800085, phone +27 82 000 0000, card 4111111111111111"
    leaks = find_pii_leaks(text)
    assert "south_african_id" in leaks or "generic_long_number" in leaks


def test_validate_flags_unchanged_pii():
    original = "Email john@example.com, phone +27 82 000 0000"
    result = validate_redaction(original, original)
    assert result.safe is False


def test_validate_accepts_placeholder_output():
    original = "Email john@example.com, phone +27 82 000 0000"
    candidate = "Email [REDACTED], phone [REDACTED]"
    result = validate_redaction(original, candidate)
    assert result.safe is True
    assert REDACTION_PLACEHOLDER in candidate


def test_build_prompt_contains_rules():
    prompt = build_redaction_prompt("hello")
    assert "strict redaction engine" in prompt
    assert "hello" in prompt

def test_deterministic_redact_masks_email_phone_card():
    text = "Email john@example.com phone +27 82 000 0000 card 4111111111111111"
    out = deterministic_redact(text)
    assert "[REDACTED]" in out
    assert "john@example.com" not in out
    assert "+27 82 000 0000" not in out
    assert "4111111111111111" not in out


def test_safe_redact_output_falls_back_when_needed():
    original = "Johann Venter, ID 9001015800085, phone +27 82 000 0000"
    bad = original  # model echoed input unchanged
    out = safe_redact_output(original, bad)
    assert "[REDACTED]" in out
    assert "9001015800085" not in out
