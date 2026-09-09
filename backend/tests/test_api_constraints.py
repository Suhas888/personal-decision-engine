import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.core import UserProfile, DynamicConstraint
from app.schemas.constraints import ConstraintIR, ConstraintType, ConstraintScope, ConstraintStrength
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database.core import Base, get_db

client = TestClient(app)

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.clear()
    session.close()

def setup_db(db_session):
    profile = UserProfile(user_id="default_user", name="Test")
    db_session.add(profile)
    db_session.commit()

@pytest.fixture
def mock_auth():
    class MockUser:
        id = "test_user"
        user_id = "test_user"
    with patch("app.api.routes.constraints.get_current_user", return_value=MockUser()):
        yield

@pytest.fixture
def mock_llm_parse_constraints():
    def fake_parse(text):
        if "unsupported" in text.lower():
            raise ValueError("I want my productivity to depend on my mood")
        if "math" in text.lower():
            return [ConstraintIR(
                type=ConstraintType.MAX_DAILY_HOURS,
                scope=ConstraintScope.GLOBAL,
                target_identifier=None,
                parameters={"max_minutes": 60, "days": ["Monday"]},
                strength=ConstraintStrength.HARD
            )]
        return []
    with patch("app.api.routes.constraints.parse_constraints_from_text", side_effect=fake_parse):
        yield

def test_constraint_crud(db_session, mock_auth):
    setup_db(db_session)
    ir = {
        "type": "MAX_DAILY_HOURS",
        "scope": "GLOBAL",
        "target_identifier": None,
        "parameters": {"max_minutes": 120},
        "strength": "HARD"
    }
    # Create
    res = client.post("/api/constraints/", json={"constraint": ir})
    if res.status_code != 200:
        print("ERROR response:", res.json())
    assert res.status_code == 200
    c_id = res.json()["id"]
    
    # Get
    res = client.get(f"/api/constraints/{c_id}")
    assert res.status_code == 200
    assert res.json()["type"] == "MAX_DAILY_HOURS"
    
    # Disable
    res = client.patch(f"/api/constraints/{c_id}/disable")
    assert res.status_code == 200
    assert not client.get(f"/api/constraints/{c_id}").json()["enabled"]

    # Delete
    res = client.delete(f"/api/constraints/{c_id}")
    assert res.status_code == 200
    assert client.get(f"/api/constraints/{c_id}").status_code == 404

def test_constraint_preview(db_session, mock_auth, mock_llm_parse_constraints):
    setup_db(db_session)
    res = client.post("/api/constraints/preview", json={"message": "no math during lunch"})
    print("PREVIEW RESULT:", res.json())
    assert res.status_code == 200
    assert res.json()["supported"] is True
    assert res.json()["constraint"]["type"] == "MAX_DAILY_HOURS"
    assert len(res.json()["conflicts"]) == 0

def test_constraint_unsupported(db_session, mock_auth, mock_llm_parse_constraints):
    setup_db(db_session)
    res = client.post("/api/constraints/preview", json={"message": "unsupported behavior please"})
    assert res.status_code == 200
    assert res.json()["supported"] is False
    assert res.json()["clarification_needed"] is True

def test_constraint_conflict(db_session, mock_auth, mock_llm_parse_constraints):
    setup_db(db_session)
    # create existing math rule manually
    db_session.add(DynamicConstraint(
        user_id="default_user", type="MAX_DAILY_HOURS", scope="GLOBAL", target=None,
        parameters={"max_minutes": 120, "days": ["Monday"]}, strength="HARD", enabled=True, source="SYSTEM"
    ))
    db_session.commit()
    
    res = client.post("/api/constraints/preview", json={"message": "no math during lunch"})
    if res.status_code != 200:
        print("ERROR response:", res.json())
    assert res.status_code == 200
    assert len(res.json()["conflicts"]) > 0
    assert res.json()["supported"] is True # It is structurally supported, just conflicts
