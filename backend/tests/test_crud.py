from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_crud_tasks():
    # Create task
    response = client.post("/api/tasks/", json={
        "title": "Test Task",
        "estimated_minutes": 60,
        "priority": 1
    })
    assert response.status_code == 200
    task_id = response.json()["id"]

    # Read tasks
    response = client.get("/api/tasks/")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Update task
    response = client.put(f"/api/tasks/{task_id}", json={
        "title": "Updated Task",
        "estimated_minutes": 60,
        "priority": 1
    })
    assert response.status_code == 200
    assert response.json()["title"] == "Updated Task"

    # Delete task
    response = client.delete(f"/api/tasks/{task_id}")
    assert response.status_code == 200

    # Verify deletion
    response = client.get("/api/tasks/")
    assert len(response.json()) == 0

def test_crud_events():
    # Create event
    response = client.post("/api/events/", json={
        "title": "Fixed Event",
        "day_of_week": "Monday",
        "start_time": 600,
        "end_time": 720
    })
    assert response.status_code == 200
    event_id = response.json()["id"]

    # Read events
    response = client.get("/api/events/")
    assert response.status_code == 200
    assert len(response.json()) == 1

    # Delete event
    response = client.delete(f"/api/events/{event_id}")
    assert response.status_code == 200

def test_crud_preferences():
    # Create pref
    response = client.put("/api/preferences/", json={
        "key": "theme",
        "value": "dark"
    })
    assert response.status_code == 200

    # Read prefs
    response = client.get("/api/preferences/")
    assert response.status_code == 200
    assert len(response.json()) >= 1
    assert any(p["key"] == "theme" and p["value"] == "dark" for p in response.json())
