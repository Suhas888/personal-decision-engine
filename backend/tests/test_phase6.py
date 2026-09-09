import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.core import UserProfile, Task, TaskDependency
from app.schemas.core import TaskCreate

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db(_sqlite_session_factory):
    """Seed a user profile into the shared SQLite DB before each test."""
    db = _sqlite_session_factory()
    db.add(UserProfile(user_id="default_user", name="Test User", max_focus_block_minutes=60))
    db.commit()
    db.close()
    yield
    # Clean up
    db2 = _sqlite_session_factory()
    db2.query(TaskDependency).delete()
    db2.query(Task).delete()
    db2.query(UserProfile).delete()
    db2.commit()
    db2.close()


def test_circular_dependency_rejection():
    # Create Task A
    res_a = client.post("/api/tasks/", json={
        "title": "Task A",
        "estimated_minutes": 60,
        "priority": 3
    })
    assert res_a.status_code == 200
    task_a_id = res_a.json()["id"]

    # Create Task B depending on Task A
    res_b = client.post("/api/tasks/", json={
        "title": "Task B",
        "estimated_minutes": 60,
        "priority": 3,
        "dependencies": [task_a_id]
    })
    assert res_b.status_code == 200
    task_b_id = res_b.json()["id"]

    # Try to update Task A to depend on Task B (creating a cycle: A -> B -> A)
    res_a_update = client.put(f"/api/tasks/{task_a_id}", json={
        "title": "Task A updated",
        "estimated_minutes": 60,
        "priority": 3,
        "dependencies": [task_b_id]
    })
    
    # Should be rejected with 400 Bad Request
    assert res_a_update.status_code == 400
    assert "Circular dependency" in res_a_update.json()["detail"]


def test_energy_requirement_parsing():
    # Test creating a task with energy requirement
    res = client.post("/api/tasks/", json={
        "title": "High Energy Task",
        "estimated_minutes": 120,
        "priority": 1,
        "energy_requirement": "high"
    })
    assert res.status_code == 200
    assert res.json()["energy_requirement"] == "high"
    
def test_optimizer_runs_with_phase6():
    # Add tasks
    client.post("/api/tasks/", json={
        "title": "Low Energy Task",
        "estimated_minutes": 60,
        "priority": 3,
        "energy_requirement": "low"
    })
    # Run plan generation
    res = client.post("/api/plan/generate", json={"week_start": "2026-09-07"})
    assert res.status_code == 200
    data = res.json()
    assert "objective_score" in data
    
    # Check that explanation is generated
    blocks = data.get("scheduled_blocks", [])
    if blocks:
        assert "explanation" in blocks[0]
