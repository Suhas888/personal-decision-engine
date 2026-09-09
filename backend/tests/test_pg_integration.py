import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.config import settings
from app.main import app
from app.database.core import get_db, Base
from app.models.core import User, UserProfile, Task, FixedEvent, Preference, DynamicConstraint

engine = create_engine(settings.DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides.clear()
app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(scope="module", autouse=True)
def setup_pg_db():
    # We don't drop/create since the DB is managed by Alembic
    # Just clear data
    db = TestingSessionLocal()
    try:
        db.query(Task).delete()
        db.query(FixedEvent).delete()
        db.query(Preference).delete()
        db.query(DynamicConstraint).delete()
        db.query(UserProfile).delete()
        db.query(User).delete()
        db.commit()
    finally:
        db.close()
    yield

def test_pg_full_crud():
    from app.api.dependencies import get_current_user
    app.dependency_overrides.pop(get_current_user, None)
    
    # 1. Create User via Auth endpoint
    res = client.post("/api/auth/register", json={
        "email": "pg_user@test.com",
        "password": "StrongPassword123!"
    })
    assert res.status_code == 201, res.text
    
    # Login to get token
    res = client.post("/api/auth/login", json={
        "email": "pg_user@test.com",
        "password": "StrongPassword123!"
    })
    assert res.status_code == 200, res.text
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get Profile
    res = client.get("/api/profile/profile", headers=headers)
    assert res.status_code == 200, res.text

    # 3. Create Task
    res = client.post("/api/tasks/", json={
        "title": "PG Task",
        "estimated_minutes": 60,
        "priority": 1,
        "category": "work"
    }, headers=headers)
    assert res.status_code == 200, res.text
    task_id = res.json()["id"]

    # 4. Create Event
    res = client.post("/api/events/", json={
        "title": "PG Event",
        "day_of_week": "Monday",
        "start_time": 600,
        "end_time": 660,
        "recurring": True
    }, headers=headers)
    assert res.status_code == 200, res.text

    # End of CRUD tests.
