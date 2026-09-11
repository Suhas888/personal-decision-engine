"""
PostgreSQL integration tests — CRUD operations.

Tests task, event, preference, and constraint CRUD
via HTTP API against real PostgreSQL (pde_test schema).
All tests use real JWT auth (pg_user_a fixture).
"""

import pytest
from datetime import datetime, timezone

pytestmark = pytest.mark.pg


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

class TestTasksCRUD:
    def test_create_task(self, pg_client, pg_user_a):
        res = pg_client.post("/api/tasks/", json={
            "title": "Write report",
            "estimated_minutes": 60,
            "priority": 1,
        }, headers=pg_user_a["headers"])
        assert res.status_code in (200, 201)
        data = res.json()
        assert data["title"] == "Write report"
        assert data["estimated_minutes"] == 60
        assert "id" in data

    def test_list_tasks(self, pg_client, pg_user_a):
        pg_client.post("/api/tasks/", json={"title": "Task A", "estimated_minutes": 30, "priority": 1},
                       headers=pg_user_a["headers"])
        pg_client.post("/api/tasks/", json={"title": "Task B", "estimated_minutes": 45, "priority": 1},
                       headers=pg_user_a["headers"])
        res = pg_client.get("/api/tasks/", headers=pg_user_a["headers"])
        assert res.status_code == 200
        titles = [t["title"] for t in res.json()]
        assert "Task A" in titles
        assert "Task B" in titles

    def test_update_task(self, pg_client, pg_user_a):
        create_res = pg_client.post("/api/tasks/", json={
            "title": "Old Title", "estimated_minutes": 30, "priority": 1
        }, headers=pg_user_a["headers"])
        task_id = create_res.json()["id"]

        update_res = pg_client.put(f"/api/tasks/{task_id}", json={
            "title": "New Title", "estimated_minutes": 90, "priority": 1
        }, headers=pg_user_a["headers"])
        assert update_res.status_code == 200
        assert update_res.json()["title"] == "New Title"
        assert update_res.json()["estimated_minutes"] == 90

    def test_delete_task(self, pg_client, pg_user_a):
        create_res = pg_client.post("/api/tasks/", json={
            "title": "To Delete", "estimated_minutes": 20, "priority": 1
        }, headers=pg_user_a["headers"])
        task_id = create_res.json()["id"]

        del_res = pg_client.delete(f"/api/tasks/{task_id}", headers=pg_user_a["headers"])
        assert del_res.status_code == 200

        # Verify it's gone
        list_res = pg_client.get("/api/tasks/", headers=pg_user_a["headers"])
        ids = [t["id"] for t in list_res.json()]
        assert task_id not in ids

    def test_task_completion_lifecycle(self, pg_client, pg_user_a):
        create_res = pg_client.post("/api/tasks/", json={
            "title": "Finish me", "estimated_minutes": 30, "priority": 1
        }, headers=pg_user_a["headers"])
        task_id = create_res.json()["id"]

        # 1. Incomplete -> Complete
        update_res = pg_client.put(f"/api/tasks/{task_id}", json={
            "title": "Finish me", "estimated_minutes": 30, "priority": 1, "completed": True
        }, headers=pg_user_a["headers"])
        assert update_res.status_code == 200
        assert update_res.json()["completed"] is True

        # 2. Persists after reload
        get_res = pg_client.get("/api/tasks/", headers=pg_user_a["headers"])
        tasks = [t for t in get_res.json() if t["id"] == task_id]
        assert tasks[0]["completed"] is True

        # 3. Excluded from planning
        plan_res = pg_client.post("/api/plan/generate", json={"week_start": "2026-09-07"}, headers=pg_user_a["headers"])
        scheduled_task_ids = [b.get("task_id") for b in plan_res.json().get("scheduled_blocks", [])]
        assert task_id not in scheduled_task_ids

        # 4. Complete -> Incomplete
        update_res2 = pg_client.put(f"/api/tasks/{task_id}", json={
            "title": "Finish me", "estimated_minutes": 30, "priority": 1, "completed": False
        }, headers=pg_user_a["headers"])
        assert update_res2.json()["completed"] is False

        # 5. Included in planning
        plan_res2 = pg_client.post("/api/plan/generate", json={"week_start": "2026-09-07"}, headers=pg_user_a["headers"])
        scheduled_task_ids2 = [b.get("task_id") for b in plan_res2.json().get("scheduled_blocks", [])]
        assert task_id in scheduled_task_ids2

    def test_task_ownership_query_filter(self, pg_client, pg_user_a, pg_user_b):
        """Tasks listed for user A must not include user B's tasks."""
        pg_client.post("/api/tasks/", json={"title": "A's Task", "estimated_minutes": 30, "priority": 1},
                       headers=pg_user_a["headers"])
        pg_client.post("/api/tasks/", json={"title": "B's Task", "estimated_minutes": 30, "priority": 1},
                       headers=pg_user_b["headers"])

        a_tasks = pg_client.get("/api/tasks/", headers=pg_user_a["headers"]).json()
        b_tasks = pg_client.get("/api/tasks/", headers=pg_user_b["headers"]).json()

        a_titles = [t["title"] for t in a_tasks]
        b_titles = [t["title"] for t in b_tasks]

        assert "A's Task" in a_titles
        assert "B's Task" not in a_titles
        assert "B's Task" in b_titles
        assert "A's Task" not in b_titles


# ---------------------------------------------------------------------------
# Fixed Events
# ---------------------------------------------------------------------------

class TestEventsCRUD:
    def test_create_event(self, pg_client, pg_user_a):
        res = pg_client.post("/api/events/", json={
            "title": "Team Meeting", "day_of_week": "Monday", "start_time": 540, "end_time": 600,
        }, headers=pg_user_a["headers"])
        assert res.status_code in (200, 201)
        data = res.json()
        assert data["title"] == "Team Meeting"

    def test_list_events(self, pg_client, pg_user_a):
        pg_client.post("/api/events/", json={
            "title": "Standup", "day_of_week": "Monday", "start_time": 540, "end_time": 600,
        }, headers=pg_user_a["headers"])
        res = pg_client.get("/api/events/", headers=pg_user_a["headers"])
        assert res.status_code == 200
        titles = [e["title"] for e in res.json()]
        assert "Standup" in titles

    def test_delete_event(self, pg_client, pg_user_a):
        create_res = pg_client.post("/api/events/", json={
            "title": "Delete Me", "day_of_week": "Monday", "start_time": 540, "end_time": 600,
        }, headers=pg_user_a["headers"])
        event_id = create_res.json()["id"]

        del_res = pg_client.delete(f"/api/events/{event_id}", headers=pg_user_a["headers"])
        assert del_res.status_code == 200

        list_res = pg_client.get("/api/events/", headers=pg_user_a["headers"])
        ids = [e["id"] for e in list_res.json()]
        assert event_id not in ids

    def test_event_ownership_isolation(self, pg_client, pg_user_a, pg_user_b):
        pg_client.post("/api/events/", json={
            "title": "A Event", "day_of_week": "Monday", "start_time": 540, "end_time": 600,
        }, headers=pg_user_a["headers"])
        pg_client.post("/api/events/", json={
            "title": "B Event", "day_of_week": "Monday", "start_time": 540, "end_time": 600,
        }, headers=pg_user_b["headers"])

        a_events = [e["title"] for e in pg_client.get("/api/events/", headers=pg_user_a["headers"]).json()]
        b_events = [e["title"] for e in pg_client.get("/api/events/", headers=pg_user_b["headers"]).json()]

        assert "A Event" in a_events
        assert "B Event" not in a_events
        assert "B Event" in b_events
        assert "A Event" not in b_events


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

class TestPreferencesCRUD:
    def test_set_and_get_preference(self, pg_client, pg_user_a):
        res = pg_client.put("/api/preferences/", json={
            "key": "theme", "value": "dark"
        }, headers=pg_user_a["headers"])
        assert res.status_code in (200, 201)
        assert res.json()["value"] == "dark"

    def test_update_preference(self, pg_client, pg_user_a):
        pg_client.put("/api/preferences/", json={"key": "lang", "value": "en"},
                       headers=pg_user_a["headers"])
        res = pg_client.put("/api/preferences/", json={"key": "lang", "value": "fr"},
                             headers=pg_user_a["headers"])
        assert res.status_code in (200, 201)
        # After upsert, value should be updated
        list_res = pg_client.get("/api/preferences/", headers=pg_user_a["headers"])
        prefs = {p["key"]: p["value"] for p in list_res.json()}
        assert prefs.get("lang") == "fr"

    def test_same_key_different_users_allowed(self, pg_client, pg_user_a, pg_user_b):
        """Same preference key for different users must be independently stored."""
        ra = pg_client.put("/api/preferences/", json={"key": "timezone", "value": "UTC"},
                            headers=pg_user_a["headers"])
        rb = pg_client.put("/api/preferences/", json={"key": "timezone", "value": "Asia/Tokyo"},
                            headers=pg_user_b["headers"])
        assert ra.status_code in (200, 201)
        assert rb.status_code in (200, 201)

        # Each user gets their own value
        a_prefs = {p["key"]: p["value"] for p in
                   pg_client.get("/api/preferences/", headers=pg_user_a["headers"]).json()}
        b_prefs = {p["key"]: p["value"] for p in
                   pg_client.get("/api/preferences/", headers=pg_user_b["headers"]).json()}

        assert a_prefs["timezone"] == "UTC"
        assert b_prefs["timezone"] == "Asia/Tokyo"

    def test_list_preferences(self, pg_client, pg_user_a):
        pg_client.put("/api/preferences/", json={"key": "color", "value": "blue"},
                       headers=pg_user_a["headers"])
        pg_client.put("/api/preferences/", json={"key": "font_size", "value": "14"},
                       headers=pg_user_a["headers"])
        res = pg_client.get("/api/preferences/", headers=pg_user_a["headers"])
        assert res.status_code == 200
        keys = [p["key"] for p in res.json()]
        assert "color" in keys
        assert "font_size" in keys


# ---------------------------------------------------------------------------
# Dynamic Constraints
# ---------------------------------------------------------------------------

class TestConstraintsCRUD:
    def _base_constraint(self):
        return {
            "constraint": {
                "type": "MAX_DAILY_HOURS",
                "scope": "GLOBAL",
                "target_identifier": None,
                "parameters": {"max_minutes": 240},
                "strength": "HARD",
            }
        }

    def test_create_constraint(self, pg_client, pg_user_a):
        from app.api.dependencies import get_current_user

        # Mock auth for constraint endpoint (uses get_current_user from routes/constraints.py)
        from unittest.mock import patch

        res = pg_client.post("/api/constraints/", json=self._base_constraint(), headers=pg_user_a["headers"])

        assert res.status_code == 200
        assert "id" in res.json()

    def test_list_constraints(self, pg_client, pg_user_a, pg_session):
        from app.models.core import DynamicConstraint
        pg_session.add(DynamicConstraint(
            user_id=pg_user_a["id"],
            type="MAX_DAILY_HOURS",
            scope="GLOBAL",
            parameters={"max_minutes": 120},
            strength="HARD",
        ))
        pg_session.commit()

        from unittest.mock import patch

        res = pg_client.get("/api/constraints/", headers=pg_user_a["headers"])

        assert res.status_code == 200
        assert len(res.json()) >= 1
