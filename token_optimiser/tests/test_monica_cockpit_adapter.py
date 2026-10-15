#!/usr/bin/env python3
"""
Focused tests for MonicaCockpitAdapter — read-only operations only.

Tests verify:
- mail_overview returns read/draft only, no send/delete
- repo_task_overview is read-only
- allowlisted_panels filters non-allowlisted and normalizes keys

Constraints enforced:
- No network calls
- Feature flag COCKPIT_MONICA_ENABLED not changed
- No repository writes, mail send/delete, or Grafana credentials

Usage:
    python -m pytest token_optimiser/tests/test_monica_cockpit_adapter.py -v
"""

import os
from unittest.mock import MagicMock

# Set test DB path before adapter import
os.environ.setdefault("COCKPIT_DB_PATH", "/tmp/test-cockpit-adapter.sqlite")

# Feature flag must remain unset (default false) - do not set COCKPIT_MONICA_ENABLED


class TestMailOverview:
    """Tests for MonicaCockpitAdapter.mail_overview() read-only behavior."""

    def test_mail_overview_returns_defaults(self):
        """mail_overview returns dict with expected defaults."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        result = adapter.mail_overview()

        assert isinstance(result, dict), "mail_overview must return a dict"
        assert "unread_count" in result, "result must contain unread_count"
        assert "mode" in result, "result must contain mode"
        assert "send_allowed" in result, "result must contain send_allowed flag"
        assert "delete_allowed" in result, "result must contain delete_allowed flag"

    def test_mail_overview_unread_count_zero(self):
        """mail_overview unread_count is zero for safety (read-only mock)."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        result = adapter.mail_overview()

        assert result["unread_count"] == 0, "unread_count should be 0 (mock, no real mail)"

    def test_mail_overview_mode_read_and_draft_only(self):
        """mail_overview mode is always 'read_and_draft_only'."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        result = adapter.mail_overview()

        assert result["mode"] == "read_and_draft_only", "mode must be read_and_draft_only"

    def test_mail_overview_send_not_allowed(self):
        """SECURITY: send_allowed must be False — no mail sending."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        result = adapter.mail_overview()

        assert result["send_allowed"] is False, "SECURITY: send_allowed must be False"

    def test_mail_overview_delete_not_allowed(self):
        """SECURITY: delete_allowed must be False — no mail deletion."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        result = adapter.mail_overview()

        assert result["delete_allowed"] is False, "SECURITY: delete_allowed must be False"


class TestRepoTaskOverview:
    """Tests for MonicaCockpitAdapter.repo_task_overview() read-only behavior."""

    def test_repo_task_overview_read_only(self):
        """repo_task_overview returns read-only mode and write_allowed=False."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        result = adapter.repo_task_overview()

        assert isinstance(result, dict), "repo_task_overview must return a dict"
        assert result["mode"] == "read_only_adapter", "mode must be read_only_adapter"
        assert result["write_allowed"] is False, "write_allowed must be False (read-only)"

    def test_repo_task_overview_accepts_repo_roots(self):
        """repo_task_overview accepts optional repo_roots parameter."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        # Test with None (default)
        result = adapter.repo_task_overview(repo_roots=None)
        assert "repo_roots" in result, "result must contain repo_roots"
        assert result["repo_roots"] == [], "repo_roots should be empty list when None"

    def test_repo_task_overview_accepts_specific_roots(self):
        """repo_task_overview returns provided repo_roots."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()
        test_roots = ["/home/user/project-a", "/home/user/project-b"]

        result = adapter.repo_task_overview(repo_roots=test_roots)

        assert result["repo_roots"] == test_roots, "repo_roots should match input"


class TestAllowlistedPanels:
    """Tests for MonicaCockpitAdapter.allowlisted_panels() filtering behavior."""

    def test_allowlisted_panels_filters_non_allowlisted(self):
        """allowlisted_panels excludes rows where allowlisted is False."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        input_rows = [
            {"name": "Panel A", "url": "https://a.example.com", "grafana_uid": "uid-a", "allowlisted": True},
            {"name": "Panel B", "url": "https://b.example.com", "grafana_uid": "uid-b", "allowlisted": False},
            {"name": "Panel C", "url": "https://c.example.com", "grafana_uid": "uid-c", "allowlisted": True},
        ]

        result = adapter.allowlisted_panels(input_rows)

        assert len(result) == 2, "Only allowlisted panels should be returned"
        names = [r["name"] for r in result]
        assert "Panel A" in names, "Panel A should be included (allowlisted=True)"
        assert "Panel C" in names, "Panel C should be included (allowlisted=True)"
        assert "Panel B" not in names, "Panel B should be excluded (allowlisted=False)"

    def test_allowlisted_panels_normalizes_keys(self):
        """allowlisted_panels normalizes output keys: grafana_uid → uid."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        input_rows = [
            {"name": "Test Panel", "url": "https://test.example.com", "grafana_uid": "test-uid-123", "allowlisted": True},
        ]

        result = adapter.allowlisted_panels(input_rows)

        assert len(result) == 1, "Should return one panel"
        assert "name" in result[0], "Result must contain 'name' key"
        assert "url" in result[0], "Result must contain 'url' key"
        assert "uid" in result[0], "Result must contain 'uid' key (normalized from grafana_uid)"
        assert result[0]["uid"] == "test-uid-123", "uid should have grafana_uid value"

    def test_allowlisted_panels_handles_empty_input(self):
        """allowlisted_panels returns empty list for None or empty input."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        # Test with None
        result_none = adapter.allowlisted_panels(None)
        assert result_none == [], "Should return [] for None input"

        # Test with empty list
        result_empty = adapter.allowlisted_panels([])
        assert result_empty == [], "Should return [] for empty list input"

    def test_allowlisted_panels_handles_missing_grafana_uid(self):
        """allowlisted_panels handles missing grafana_uid gracefully."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        input_rows = [
            {"name": "Panel X", "url": "https://x.example.com", "allowlisted": True},
        ]

        result = adapter.allowlisted_panels(input_rows)

        assert len(result) == 1, "Should return the allowlisted panel"
        assert result[0]["uid"] is None, "uid should be None when grafana_uid is missing"

    def test_allowlisted_panels_preserves_all_allowlisted(self):
        """allowlisted_panels includes all rows with allowlisted=True."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        input_rows = [
            {"name": f"Panel-{i}", "url": f"https://panel{i}.com", "grafana_uid": f"uid-{i}", "allowlisted": True}
            for i in range(5)
        ]

        result = adapter.allowlisted_panels(input_rows)

        assert len(result) == 5, "All 5 allowlisted panels should be returned"


class TestAdapterInstantiation:
    """Tests for adapter instantiation and dependencies."""

    def test_adapter_instantiates_with_db_factory(self):
        """MonicaCockpitAdapter accepts optional db_factory parameter."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        # Test default instantiation
        adapter = MonicaCockpitAdapter()
        assert adapter is not None

        # Test with explicit db_factory
        mock_factory = MagicMock()
        adapter_with_factory = MonicaCockpitAdapter(db_factory=mock_factory)
        assert adapter_with_factory is not None

    def test_adapter_has_required_methods(self):
        """Adapter has all required public methods."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        assert hasattr(adapter, "mail_overview"), "Must have mail_overview method"
        assert hasattr(adapter, "repo_task_overview"), "Must have repo_task_overview method"
        assert hasattr(adapter, "allowlisted_panels"), "Must have allowlisted_panels method"


class TestSecurityConstraintsVerification:
    """Verification that security constraints cannot be bypassed."""

    def test_no_send_method_exists(self):
        """Adapter should NOT have a send_mail method."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        # Check that no send or delete methods exist
        assert not hasattr(adapter, "send_mail"), "send_mail method should not exist"
        assert not hasattr(adapter, "delete_mail"), "delete_mail method should not exist"
        assert not hasattr(adapter, "send"), "send method should not exist"
        assert not hasattr(adapter, "delete"), "delete method should not exist"

    def test_no_write_methods_on_repo(self):
        """Adapter should NOT have repo write methods."""
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter

        adapter = MonicaCockpitAdapter()

        # Check for absence of write methods
        assert not hasattr(adapter, "create_task"), "create_task should not be a direct method"
        assert not hasattr(adapter, "edit_task"), "edit_task should not be a direct method"
        assert not hasattr(adapter, "delete_task"), "delete_task should not be a direct method"