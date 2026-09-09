import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.core import Base
from app.models.core import DynamicConstraint

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_create_and_retrieve_constraint(db_session):
    constraint = DynamicConstraint(
        user_id="user1",
        version="1.0",
        type="MAX_DAILY_HOURS",
        scope="GLOBAL",
        target=None,
        parameters={"max_minutes": 300, "days": ["Monday"]},
        strength="HARD",
        enabled=True,
        source="USER"
    )
    db_session.add(constraint)
    db_session.commit()

    retrieved = db_session.query(DynamicConstraint).filter_by(user_id="user1").first()
    assert retrieved is not None
    assert retrieved.type == "MAX_DAILY_HOURS"
    assert retrieved.parameters["max_minutes"] == 300
    assert retrieved.parameters["days"] == ["Monday"]

def test_update_constraint(db_session):
    constraint = DynamicConstraint(user_id="user1", type="AVOID_TIME", parameters={"start": 0, "end": 60})
    db_session.add(constraint)
    db_session.commit()

    c = db_session.query(DynamicConstraint).first()
    c.parameters = {"start": 60, "end": 120}
    db_session.commit()

    updated = db_session.query(DynamicConstraint).first()
    assert updated.parameters["start"] == 60

def test_enable_disable_constraint(db_session):
    constraint = DynamicConstraint(user_id="user1", type="FORCE_DAY", enabled=True)
    db_session.add(constraint)
    db_session.commit()

    c = db_session.query(DynamicConstraint).first()
    assert c.enabled is True
    
    c.enabled = False
    db_session.commit()

    updated = db_session.query(DynamicConstraint).first()
    assert updated.enabled is False

def test_delete_constraint(db_session):
    constraint = DynamicConstraint(user_id="user1", type="FORCE_DAY")
    db_session.add(constraint)
    db_session.commit()
    
    assert db_session.query(DynamicConstraint).count() == 1
    db_session.delete(constraint)
    db_session.commit()
    assert db_session.query(DynamicConstraint).count() == 0

def test_user_ownership_isolation(db_session):
    c1 = DynamicConstraint(user_id="user1", type="MAX_DAILY_HOURS")
    c2 = DynamicConstraint(user_id="user2", type="MAX_DAILY_HOURS")
    db_session.add_all([c1, c2])
    db_session.commit()

    user1_constraints = db_session.query(DynamicConstraint).filter_by(user_id="user1").all()
    assert len(user1_constraints) == 1
    assert user1_constraints[0].user_id == "user1"
