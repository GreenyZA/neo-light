"""Monica cockpit router + persistence helpers (feature-flagged).

This module is registered from ``token_optimiser/dashboard/app.py`` only when the
``COCKPIT_MONICA_ENABLED`` feature flag is true.  It never sends or deletes mail
and never writes to source repositories; those actions remain approval-gated.
"""


import json
import os
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field


ROUTER = APIRouter()


class TaskUpsert(BaseModel):
    id: Optional[int] = None
    title: str
    status: str = "open"
    priority: str = "medium"
    due_at: Optional[str] = None
    source_repo: Optional[str] = None
    assignee: Optional[str] = "Monica"
    task_id: Optional[str] = None


class ReminderUpsert(BaseModel):
    id: Optional[int] = None
    title: str
    fire_at: Optional[str] = None
    channel: str = "log"
    status: str = "scheduled"


class PanelUpsert(BaseModel):
    name: str
    grafana_uid: Optional[str] = None
    url: str
    allowlisted: bool = False


def _db_path() -> Path:
    raw = os.environ.get("COCKPIT_DB_PATH", "~/.local/state/monica-cockpit/cockpit.sqlite")
    p = Path(raw).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def _conn():
    from token_optimiser.db.cockpit_schema import ensure_schema

    conn = sqlite3.connect(str(_db_path()), timeout=5.0)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    return conn


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _api_ok(data: Any = None, msg: str = "ok") -> JSONResponse:
    return JSONResponse(content={"ok": True, "data": data, "msg": msg}, status_code=200)


def _api_err(msg: str, code: int = 400, data: Any = None) -> JSONResponse:
    return JSONResponse(content={"ok": False, "msg": msg, "data": data}, status_code=code)


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {k: row[k] for k in row.keys()}


def _coerce_bool(value: Any) -> int:
    return 1 if bool(value) else 0


# ── Page shell ─────────────────────────────────────────────────────────────────


@ROUTER.get("/cockpit/monica")
def monica_page():
    path = Path(__file__).parent / "static" / "cockpit_monica.html"
    if not path.exists():
        return JSONResponse(content={"error": "not found"}, status_code=404)
    return FileResponse(path)


# ── State ─────────────────────────────────────────────────────────────────────


@ROUTER.get("/api/cockpit/monica/state")
def monica_state():
    conn = _conn()
    try:
        rows = list(conn.execute("SELECT * FROM cockpit_events ORDER BY id DESC LIMIT 20"))
        events = [_row_to_dict(r) for r in rows]
        tasks = [dict(r) for r in conn.execute("SELECT * FROM cockpit_tasks ORDER BY updated_at DESC").fetchall()]
        reminders = [dict(r) for r in conn.execute("SELECT * FROM cockpit_reminders ORDER BY fire_at IS NULL, fire_at").fetchall()]
        panels = [dict(r) for r in conn.execute("SELECT * FROM cockpit_panels ORDER BY id").fetchall()]
        counts = conn.execute(
            "SELECT status, COUNT(*) AS n FROM cockpit_tasks GROUP BY status"
        ).fetchall()
        status_counts = {r["status"]: r["n"] for r in counts}
        from token_optimiser.integration.monica_cockpit_adapter import MonicaCockpitAdapter
        adapter = MonicaCockpitAdapter(db_factory=_conn)
        return _api_ok(
            {
                "events": events,
                "tasks": tasks,
                "task_counts": status_counts,
                "reminders": reminders,
                "panels": panels,
                "mail": adapter.mail_overview(),
                "repo_tasks": adapter.repo_task_overview(),
            }
        )
    finally:
        conn.close()


# ── Tasks ──────────────────────────────────────────────────────────────────────


@ROUTER.get("/api/cockpit/monica/tasks")
def list_tasks():
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM cockpit_tasks ORDER BY id DESC").fetchall()]
        return _api_ok(rows)
    finally:
        conn.close()


@ROUTER.post("/api/cockpit/monica/tasks")
def upsert_task(payload: TaskUpsert):
    conn = _conn()
    try:
        now = _now_iso()
        if payload.id is None:
            cur = conn.execute(
                """
                INSERT INTO cockpit_tasks (title, status, priority, due_at, source_repo, assignee, created_at, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (
                    payload.title,
                    payload.status or "open",
                    payload.priority or "medium",
                    payload.due_at,
                    payload.source_repo,
                    payload.assignee or "Monica",
                    now,
                    now,
                ),
            )
            task_id = cur.lastrowid
        else:
            conn.execute(
                """
                UPDATE cockpit_tasks SET title=?, status=?, priority=?, due_at=?, source_repo=?, assignee=?, updated_at=?
                WHERE id=?
                """,
                (
                    payload.title,
                    payload.status or "open",
                    payload.priority or "medium",
                    payload.due_at,
                    payload.source_repo,
                    payload.assignee or "Monica",
                    now,
                    payload.id,
                ),
            )
            task_id = payload.id
        conn.commit()
        return _api_ok({"id": task_id})
    finally:
        conn.close()


# ── Reminders ─────────────────────────────────────────────────────────────────


@ROUTER.get("/api/cockpit/monica/reminders")
def list_reminders():
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM cockpit_reminders ORDER BY id DESC").fetchall()]
        return _api_ok(rows)
    finally:
        conn.close()


@ROUTER.post("/api/cockpit/monica/reminders")
def upsert_reminder(payload: ReminderUpsert):
    conn = _conn()
    try:
        now = _now_iso()
        if payload.id is None:
            cur = conn.execute(
                "INSERT INTO cockpit_reminders (title, fire_at, channel, status, created_at) VALUES (?,?,?,?,?)",
                (payload.title, payload.fire_at, payload.channel or "log", payload.status or "scheduled", now),
            )
            rid = cur.lastrowid
        else:
            conn.execute(
                "UPDATE cockpit_reminders SET title=?, fire_at=?, channel=?, status=? WHERE id=?",
                (payload.title, payload.fire_at, payload.channel or "log", payload.status or "scheduled", payload.id),
            )
            rid = payload.id
        conn.commit()
        return _api_ok({"id": rid})
    finally:
        conn.close()


# ── Panels ─────────────────────────────────────────────────────────────────────


@ROUTER.get("/api/cockpit/monica/panels")
def list_panels():
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM cockpit_panels ORDER BY id").fetchall()]
        return _api_ok(rows)
    finally:
        conn.close()


@ROUTER.post("/api/cockpit/monica/panels")
def register_panel(payload: PanelUpsert):
    conn = _conn()
    try:
        now = _now_iso()
        cur = conn.execute(
            "INSERT INTO cockpit_panels (name, grafana_uid, url, allowlisted, created_at) VALUES (?,?,?,?,?)",
            (payload.name, payload.grafana_uid, payload.url, _coerce_bool(payload.allowlisted), now),
        )
        pid = cur.lastrowid
        conn.commit()
        return _api_ok({"id": pid})
    finally:
        conn.close()


@ROUTER.get("/api/cockpit/monica/apm")
def apm_proxy(request: Request):
    """Expose only allowlisted panel URLs; never embed Grafana admin credentials."""
    conn = _conn()
    try:
        rows = [dict(r) for r in conn.execute("SELECT * FROM cockpit_panels WHERE allowlisted=1").fetchall()]
        urls = [{"name": r["name"], "url": r["url"], "uid": r["grafana_uid"]} for r in rows]
        return _api_ok(urls)
    finally:
        conn.close()


# ── Registration ───────────────────────────────────────────────────────────────


def feature_enabled(flag: Optional[bool] = None) -> bool:
    if flag is not None:
        return bool(flag)
    raw = os.environ.get("COCKPIT_MONICA_ENABLED", "0")
    return raw.lower() in {"1", "true", "yes", "on"}


def register_cockpit_endpoints(app, enabled: Optional[bool] = None) -> bool:
    """Attach cockpit routes when the feature flag is active."""
    if not feature_enabled(enabled):
        return False
    app.include_router(ROUTER)
    return True
