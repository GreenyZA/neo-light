import os

os.environ.setdefault("COCKPIT_DB_PATH", "/tmp/test-cockpit.sqlite")
os.environ["COCKPIT_MONICA_ENABLED"] = "1"

from fastapi.testclient import TestClient

from token_optimiser.dashboard.app import app
from token_optimiser.dashboard.cockpit import register_cockpit_endpoints

register_cockpit_endpoints(app, enabled=True)

client = TestClient(app)


def test_cockpit_state_returns_ok():
    res = client.get("/api/cockpit/monica/state")
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "tasks" in body["data"]
    assert body["data"]["mail"]["send_allowed"] is False


def test_task_and_reminder_round_trip():
    task = client.post("/api/cockpit/monica/tasks", json={"title": "Read mail", "status": "open", "priority": "medium"})
    assert task.status_code == 200
    task_id = task.json()["data"]["id"]
    tasks = client.get("/api/cockpit/monica/tasks").json()["data"]
    assert any(t["id"] == task_id for t in tasks)

    reminder = client.post(
        "/api/cockpit/monica/reminders", json={"title": "Catchup", "channel": "log", "status": "scheduled"}
    )
    assert reminder.status_code == 200
    reminders = client.get("/api/cockpit/monica/reminders").json()["data"]
    assert any(r["title"] == "Catchup" for r in reminders)


def test_allowlisted_panel_and_apm():
    panel = client.post(
        "/api/cockpit/monica/panels",
        json={"name": "ACER GPU", "url": "http://localhost:3000/panel/1", "allowlisted": True},
    )
    assert panel.status_code == 200
    apm = client.get("/api/cockpit/monica/apm").json()["data"]
    assert any(p["name"] == "ACER GPU" for p in apm)


def test_page_shell_loads():
    res = client.get("/cockpit/monica")
    assert res.status_code == 200
    assert "Monica Cockpit" in res.text
