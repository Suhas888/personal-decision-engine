import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timezone, timedelta
from app.main import app
from app.models.core import UserProfile, Task, FixedEvent, CommandConfirmation
from unittest.mock import patch
from app.schemas.commands import Command, Operation, TargetType, Scope, FilterField, FilterOperator, CommandFilter
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
    profile = UserProfile(user_id="test_user", name="Test")
    db_session.add(profile)
    t1 = Task(user_id="test_user", title="Homework 1", estimated_minutes=30)
    t2 = Task(user_id="test_user", title="Homework 2", estimated_minutes=30)
    t3 = Task(user_id="other_user", title="Homework 3", estimated_minutes=30)
    db_session.add_all([t1, t2, t3])
    db_session.commit()

@pytest.fixture
def mock_auth():
    class MockUser:
        id = "test_user"
        user_id = "test_user"
    from app.api.routes.commands import get_current_user
    app.dependency_overrides[get_current_user] = lambda: MockUser()
    yield
    app.dependency_overrides.pop(get_current_user, None)

@pytest.fixture
def mock_llm_parse():
    # Return a dummy command instead of calling Gemini
    def fake_parse(text):
        if "delete all tasks" in text.lower():
            return [Command(operation=Operation.DELETE, target_type=TargetType.TASK, scope=Scope.ALL)]
        if "delete homework 1" in text.lower():
            return [Command(operation=Operation.DELETE, target_type=TargetType.TASK, scope=Scope.FILTERED, filters=[
                CommandFilter(field=FilterField.TITLE, operator=FilterOperator.CONTAINS, value="Homework 1")
            ])]
        return []
    with patch("app.api.routes.commands.parse_commands_from_text", side_effect=fake_parse):
        yield

def test_command_preview_delete_all(db_session, mock_auth, mock_llm_parse):
    setup_db(db_session)
    res = client.post("/api/commands/preview", json={"message": "Delete all tasks"})
    assert res.status_code == 200
    data = res.json()
    assert data["requires_confirmation"] is True
    assert data["confirmation_id"] is not None
    assert data["affected_count"] == 2 # 2 tasks for test_user

def test_command_execute_delete_all(db_session, mock_auth, mock_llm_parse):
    setup_db(db_session)
    res = client.post("/api/commands/preview", json={"message": "Delete all tasks"})
    conf_id = res.json()["confirmation_id"]
    
    # Execute
    res2 = client.post("/api/commands/execute", json={"confirmation_id": conf_id})
    assert res2.status_code == 200
    assert db_session.query(Task).filter_by(user_id="test_user").count() == 0
    
    # Replay should fail
    res3 = client.post("/api/commands/execute", json={"confirmation_id": conf_id})
    assert res3.status_code == 409

def test_command_preview_delete_filtered(db_session, mock_auth, mock_llm_parse):
    setup_db(db_session)
    res = client.post("/api/commands/preview", json={"message": "Delete homework 1"})
    assert res.status_code == 200
    assert res.json()["affected_count"] == 1
    assert res.json()["requires_confirmation"] is True # Assuming delete always requires confirmation in Validator

def test_command_expiry(db_session, mock_auth, mock_llm_parse):
    setup_db(db_session)
    res = client.post("/api/commands/preview", json={"message": "Delete all tasks"})
    conf_id = res.json()["confirmation_id"]
    
    # Manually expire
    conf = db_session.query(CommandConfirmation).filter_by(id=conf_id).first()
    conf.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()
    
    res2 = client.post("/api/commands/execute", json={"confirmation_id": conf_id})
    assert res2.status_code == 409

def test_command_ownership(db_session, mock_auth, mock_llm_parse):
    setup_db(db_session)
    res = client.post("/api/commands/preview", json={"message": "Delete all tasks"})
    conf_id = res.json()["confirmation_id"]
    
    class OtherUser:
        id = "hacker"
        user_id = "hacker"
        
    from app.api.routes.commands import get_current_user
    app.dependency_overrides[get_current_user] = lambda: OtherUser()
    try:
        res2 = client.post("/api/commands/execute", json={"confirmation_id": conf_id})
        assert res2.status_code == 404 # Confirmation not found for hacker
    finally:
        if get_current_user in app.dependency_overrides:
            del app.dependency_overrides[get_current_user]
