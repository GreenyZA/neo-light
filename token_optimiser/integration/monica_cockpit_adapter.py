"""Monica cockpit adapters (read-oriented; action requires approval)."""


from dataclasses import dataclass


@dataclass(frozen=True)
class MailOverview:
    unread_count: int = 0
    mode: str = "read_and_draft_only"
    send_allowed: bool = False
    delete_allowed: bool = False


class MonicaCockpitAdapter:
    """Composed adapter used by cockpit route handlers."""

    def __init__(self, *, db_factory=None):
        self.db_factory = db_factory

    # mail / workflow
    def mail_overview(self) -> dict:
        """Return counts and policy only; never transforms or sends messages."""
        return {
            "unread_count": 0,
            "mode": "read_and_draft_only",
            "send_allowed": False,
            "delete_allowed": False,
        }

    def repo_task_overview(self, repo_roots=None) -> dict:
        """Read-side only; no repository writes occur here."""
        return {
            "mode": "read_only_adapter",
            "write_allowed": False,
            "repo_roots": repo_roots or [],
        }

    def allowlisted_panels(self, rows):
        """Normalize panel rows into a read-only embedding list."""
        return [
            {"name": r["name"], "url": r["url"], "uid": r.get("grafana_uid")}
            for r in (rows or [])
            if bool(r.get("allowlisted"))
        ]
