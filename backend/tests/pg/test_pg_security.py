"""
PostgreSQL integration tests — Multi-user security & isolation.

Verifies that User A cannot read, modify, delete, or act on resources
owned by User B — enforced at the backend query level, not frontend filtering.

Tests exercise real HTTP API boundaries with real JWT auth.
"""

import pytest
from unittest.mock import patch

pytestmark = pytest.mark.pg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_task(pg_client, user, title="My Task"):
    res = pg_client.post("/api/tasks/", json={
        "title": title, "estimated_minutes": 30, "priority": 1
    }, headers=user["headers"])
    assert res.status_code in (200, 201), f"Failed to create task: {res.text}"
    return res.json()["id"]


def _create_event(pg_client, user, title="My Event"):
    res = pg_client.post("/api/events/", json={
        "title": title,
        "day_of_week": "Monday",
        "start_time": 540,
        "end_time": 600,
    }, headers=user["headers"])
    assert res.status_code in (200, 201), f"Failed to create event: {res.text}"
    return res.json()["id"]


def _mock_user(user_id: str):
    class _MockUser:
        pass
    _MockUser.id = user_id
    _MockUser.user_id = user_id
    return _MockUser()


# ---------------------------------------------------------------------------
# Task isolation
# ---------------------------------------------------------------------------

class TestTaskIsolation:
    def test_user_b_cannot_read_user_a_task_list(self, pg_client, pg_user_a, pg_user_b):
        _create_task(pg_client, pg_user_a, "A Private Task")
        b_tasks = pg_client.get("/api/tasks/", headers=pg_user_b["headers"]).json()
        titles = [t["title"] for t in b_tasks]
        assert "A Private Task" not in titles

    def test_user_b_cannot_update_user_a_task(self, pg_client, pg_user_a, pg_user_b):
        task_id = _create_task(pg_client, pg_user_a, "A Task")
        res = pg_client.put(f"/api/tasks/{task_id}", json={
            "title": "Hacked", "estimated_minutes": 999, "priority": 1
        }, headers=pg_user_b["headers"])
        # Must be 404 (not found for user B) — not 200
        assert res.status_code in (404, 403)

    def test_user_b_cannot_delete_user_a_task(self, pg_client, pg_user_a, pg_user_b):
        task_id = _create_task(pg_client, pg_user_a, "A Sensitive Task")
        res = pg_client.delete(f"/api/tasks/{task_id}", headers=pg_user_b["headers"])
        assert res.status_code in (404, 403)

        # Task still exists for user A
        a_tasks = pg_client.get("/api/tasks/", headers=pg_user_a["headers"]).json()
        ids = [t["id"] for t in a_tasks]
        assert task_id in ids


# ---------------------------------------------------------------------------
# Event isolation
# ---------------------------------------------------------------------------

class TestEventIsolation:
    def test_user_b_cannot_see_user_a_events(self, pg_client, pg_user_a, pg_user_b):
        _create_event(pg_client, pg_user_a, "A's Private Meeting")
        b_events = pg_client.get("/api/events/", headers=pg_user_b["headers"]).json()
        titles = [e["title"] for e in b_events]
        assert "A's Private Meeting" not in titles

    def test_user_b_cannot_delete_user_a_event(self, pg_client, pg_user_a, pg_user_b):
        event_id = _create_event(pg_client, pg_user_a, "A's Sensitive Event")
        res = pg_client.delete(f"/api/events/{event_id}", headers=pg_user_b["headers"])
        assert res.status_code in (404, 403)


# ---------------------------------------------------------------------------
# Preference isolation
# ---------------------------------------------------------------------------

class TestPreferenceIsolation:
    def test_user_b_cannot_see_user_a_preferences(self, pg_client, pg_user_a, pg_user_b):
        pg_client.post("/api/preferences/", json={"key": "secret_key", "value": "secret"},
                       headers=pg_user_a["headers"])
        b_prefs = pg_client.get("/api/preferences/", headers=pg_user_b["headers"]).json()
        keys = [p["key"] for p in b_prefs]
        assert "secret_key" not in keys


# ---------------------------------------------------------------------------
# Profile isolation
# ---------------------------------------------------------------------------

class TestProfileIsolation:
    def test_me_returns_only_own_data(self, pg_client, pg_user_a, pg_user_b):
        a_me = pg_client.get("/api/auth/me", headers=pg_user_a["headers"]).json()
        b_me = pg_client.get("/api/auth/me", headers=pg_user_b["headers"]).json()
        assert a_me["email"] == pg_user_a["email"]
        assert b_me["email"] == pg_user_b["email"]
        assert a_me["id"] != b_me["id"]


# ---------------------------------------------------------------------------
# Constraint isolation
# ---------------------------------------------------------------------------

class TestConstraintIsolation:
    def test_user_b_cannot_see_user_a_constraints(self, pg_client, pg_session, pg_user_a, pg_user_b):
        from app.models.core import DynamicConstraint
        # Insert constraint directly for user A
        c = DynamicConstraint(
            user_id=pg_user_a["id"],
            type="MAX_DAILY_HOURS",
            scope="GLOBAL",
            parameters={"max_minutes": 120},
            strength="HARD",
        )
        pg_session.add(c)
        pg_session.commit()
        pg_session.refresh(c)

        b_constraints = pg_client.get("/api/constraints/", headers=pg_user_b["headers"]).json()

        ids = [x["id"] for x in b_constraints]
        assert c.id not in ids

    def test_user_b_cannot_delete_user_a_constraint(self, pg_client, pg_session, pg_user_a, pg_user_b):
        from app.models.core import DynamicConstraint
        c = DynamicConstraint(
            user_id=pg_user_a["id"],
            type="AVOID_TIME",
            scope="GLOBAL",
            parameters={"start_minute": 0, "end_minute": 60},
            strength="SOFT",
        )
        pg_session.add(c)
        pg_session.commit()
        pg_session.refresh(c)

        res = pg_client.delete(f"/api/constraints/{c.id}", headers=pg_user_b["headers"])
        assert res.status_code in (404, 403)

        # Constraint still exists for user A
        still_there = pg_session.query(DynamicConstraint).filter_by(id=c.id).first()
        assert still_there is not None


# ---------------------------------------------------------------------------
# Command confirmation isolation
# ---------------------------------------------------------------------------

class TestCommandConfirmationIsolation:
    def test_user_b_cannot_execute_user_a_confirmation(self, pg_client, pg_session, pg_user_a, pg_user_b):
        from app.models.core import CommandConfirmation
        from datetime import datetime, timezone, timedelta
        import json

        # Insert a confirmation owned by user A
        conf = CommandConfirmation(
            user_id=pg_user_a["id"],
            command_payload=json.dumps([{"operation": "DELETE", "target_type": "TASK",
                                          "scope": "ALL", "filters": []}]),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            consumed=False,
        )
        pg_session.add(conf)
        pg_session.commit()
        pg_session.refresh(conf)

        # User B tries to execute — must fail (404 not found for user B)
        res = pg_client.post("/api/commands/execute",
                             json={"confirmation_id": str(conf.id)},
                             headers=pg_user_b["headers"])
        assert res.status_code in (404, 403, 409)

        # Confirmation not consumed
        pg_session.expire(conf)
        still = pg_session.query(CommandConfirmation).filter_by(id=conf.id).first()
        assert still is not None
        assert still.consumed is False


# ---------------------------------------------------------------------------
# Cross-token protection
# ---------------------------------------------------------------------------

class TestTokenIsolation:
    def test_user_b_token_cannot_access_user_a_protected_route(self, pg_client, pg_user_a, pg_user_b):
        """User B's JWT must not grant access to user A's data by tampering."""
        # User A's /me with User B's token → returns User B's data (not A's)
        res = pg_client.get("/api/auth/me", headers=pg_user_b["headers"])
        assert res.status_code == 200
        assert res.json()["id"] == pg_user_b["id"]
        assert res.json()["id"] != pg_user_a["id"]
