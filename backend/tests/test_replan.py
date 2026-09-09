import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.core import UserProfile, Task, FixedEvent, Plan, PlanHistory
from unittest.mock import patch
from app.services.llm_service import ParsedChangeRequest

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db(_sqlite_session_factory):
    """Seed fresh data into the shared SQLite DB before each test."""
    db = _sqlite_session_factory()
    db.add(UserProfile(user_id="default_user", name="Test User", max_focus_block_minutes=60))
    db.add(FixedEvent(user_id="default_user", title="Math Class", day_of_week="Monday", start_time=600, end_time=720))
    db.add(Task(user_id="default_user", title="Do Homework", estimated_minutes=120, priority=1))
    db.commit()
    db.close()
    yield
    # Clean up seeded data
    db2 = _sqlite_session_factory()
    db2.query(Plan).delete()
    db2.query(PlanHistory).delete()
    db2.query(Task).delete()
    db2.query(FixedEvent).delete()
    db2.query(UserProfile).delete()
    db2.commit()
    db2.close()

def test_replan_parse_mock():
    with patch("app.api.routes.replan.parse_schedule_change") as mock_parse:
        mock_parse.return_value = ParsedChangeRequest(
            action="cancel_event",
            target_type="event",
            target_name="Math Class",
            human_readable_summary="Math Class on Monday was cancelled."
        )
        response = client.post("/api/replan/parse", json={"text": "My math class is cancelled"})
        assert response.status_code == 200
        data = response.json()
        assert data["action"] == "cancel_event"
        assert data["target_name"] == "Math Class"

def test_replan_apply_cancel_event(_sqlite_session_factory):
    # 1. Generate initial plan
    initial_res = client.post("/api/plan/generate", json={"week_start": "2026-09-07"})
    assert initial_res.status_code == 200
    
    db = _sqlite_session_factory()
    assert db.query(Plan).count() == 1
    db.close()

    # 2. Apply replan
    replan_res = client.post("/api/replan/apply", json={
        "action": "cancel_event",
        "target_type": "event",
        "target_name": "Math",
        "human_readable_summary": "Math Class on Monday was cancelled.",
        "week_start": "2026-09-07"
    })
    assert replan_res.status_code == 200
    
    db = _sqlite_session_factory()
    # Check event was deleted
    assert db.query(FixedEvent).count() == 0
    # Check new plan created
    assert db.query(Plan).count() == 2
    # Check PlanHistory created
    history = db.query(PlanHistory).first()
    assert history is not None
    assert history.change_reason == "Math Class on Monday was cancelled."
    db.close()

def test_replan_apply_complete_task(_sqlite_session_factory):
    # Apply replan
    replan_res = client.post("/api/replan/apply", json={
        "action": "complete_task",
        "target_type": "task",
        "target_name": "Homework",
        "human_readable_summary": "Homework is done.",
        "week_start": "2026-09-07"
    })
    assert replan_res.status_code == 200
    
    db = _sqlite_session_factory()
    task = db.query(Task).filter(Task.title == "Do Homework").first()
    assert task.completed == True
    db.close()
