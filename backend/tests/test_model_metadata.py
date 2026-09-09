import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.database.core import Base
from app.models.core import UserProfile, Preference, ScheduleBlock, PlanHistory, User, Task, Plan

@pytest.fixture(scope="function")
def db_session():
    # Use SQLite memory for simple metadata checking
    from sqlalchemy import event
    engine = create_engine("sqlite:///:memory:")
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
        
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    # Create required parent User
    user1 = User(id="user1", email="u1@test.com", hashed_password="pw")
    user2 = User(id="user2", email="u2@test.com", hashed_password="pw")
    session.add_all([user1, user2])
    session.commit()
    
    yield session
    session.close()

def test_user_profile_uniqueness(db_session):
    p1 = UserProfile(user_id="user1", name="Alice")
    db_session.add(p1)
    db_session.commit()
    
    p2 = UserProfile(user_id="user1", name="Duplicate")
    db_session.add(p2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

def test_preference_uniqueness(db_session):
    # Same user, same key -> Rejected
    pref1 = Preference(user_id="user1", key="theme", value="dark")
    db_session.add(pref1)
    db_session.commit()
    
    pref2 = Preference(user_id="user1", key="theme", value="light")
    db_session.add(pref2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    
    # Different user, same key -> Allowed
    pref3 = Preference(user_id="user2", key="theme", value="light")
    db_session.add(pref3)
    db_session.commit()
    
def test_schedule_block_task_nullable(db_session):
    plan = Plan(id=1, user_id="user1", week_start="2026-09-07")
    db_session.add(plan)
    db_session.commit()
    
    # Can create ScheduleBlock with task_id=None (free time)
    block = ScheduleBlock(user_id="user1", plan_id=plan.id, task_id=None, block_type="free")
    db_session.add(block)
    db_session.commit()
    assert block.id is not None

def test_plan_history_nullable_plans(db_session):
    # Can create PlanHistory without previous_plan or new_plan (e.g. if deleted)
    history = PlanHistory(user_id="user1", previous_plan_id=None, new_plan_id=None, change_reason="Test")
    db_session.add(history)
    db_session.commit()
    assert history.id is not None
