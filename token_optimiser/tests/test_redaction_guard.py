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