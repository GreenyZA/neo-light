"""Schema and bootstrap for the Monica cockpit persistence layer."""

SCHEMA = r"""
CREATE TABLE IF NOT EXISTS cockpit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    kind TEXT NOT NULL,
    source TEXT,
    payload_json TEXT,
    user TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cockpit_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium',
    due_at TEXT,
    source_repo TEXT,
    assignee TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cockpit_reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    fire_at TEXT,
    channel TEXT NOT NULL DEFAULT 'log',
    status TEXT NOT NULL DEFAULT 'scheduled',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cockpit_panels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    grafana_uid TEXT,
    url TEXT NOT NULL,
    allowlisted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cockpit_events_ts ON cockpit_events(ts);
CREATE INDEX IF NOT EXISTS idx_cockpit_tasks_status ON cockpit_tasks(status);
CREATE INDEX IF NOT EXISTS idx_cockpit_reminders_fire_at ON cockpit_reminders(fire_at);
"""


def ensure_schema(conn) -> None:
    """Create all Monica cockpit tables/indexes (idempotent)."""
    conn.executescript(SCHEMA)
    conn.commit()
