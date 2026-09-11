import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.core import Base
from app.models.core import UserProfile, Task, FixedEvent, Preference
from unittest.mock import patch
from app.schemas.commands import Command, Operation, TargetType, Scope, FilterField, FilterOperator, CommandFilter
from app.services.command_executor import CommandExecutor, ExecutionResult

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def setup_db(db, user_id="user1"):
    # Create some dummy data
    t1 = Task(user_id=user_id, title="Task 1", completed=False, estimated_minutes=30, priority=1)
    t2 = Task(user_id=user_id, title="Task 2", completed=False, estimated_minutes=30, priority=2)
    t3 = Task(user_id=user_id, title="GATE prep", completed=False, estimated_minutes=60, priority=3)
    t4 = Task(user_id="other_user", title="Secret Task", completed=False, estimated_minutes=30, priority=1)
    db.add_all([t1, t2, t3, t4])
    db.commit()

def test_delete_one_task(db_session):
    setup_db(db_session)
    executor = CommandExecutor(db_session, "user1")
    cmd = Command(
        operation=Operation.DELETE, 
        target_type=TargetType.TASK, 
        scope=Scope.SINGLE, 
        filters=[CommandFilter(field=FilterField.TITLE, operator=FilterOperator.EQ, value="Task 1")]
    )
    res = executor.execute([cmd])
    assert res[0].success
    assert res[0].affected_count == 1
    # Verify remaining tasks
    assert db_session.query(Task).count() == 3

def test_delete_all_tasks(db_session):
    setup_db(db_session)
    executor = CommandExecutor(db_session, "user1")
    cmd = Command(
        operation=Operation.DELETE, 
        target_type=TargetType.TASK, 
        scope=Scope.ALL
    )
    
    res = executor.execute([cmd])
    assert res[0].success
    assert res[0].affected_count == 3 # Should only delete user1's tasks, not other_user's
    assert db_session.query(Task).count() == 1 # other_user's task remains

def test_delete_filtered_tasks(db_session):
    setup_db(db_session)
    executor = CommandExecutor(db_session, "user1")
    cmd = Command(
        operation=Operation.DELETE, 
        target_type=TargetType.TASK, 
        scope=Scope.FILTERED,
        filters=[CommandFilter(field=FilterField.TITLE, operator=FilterOperator.CONTAINS, value="Task")]
    )
    
    res = executor.execute([cmd])
    assert res[0].success
    assert res[0].affected_count == 2 # Task 1, Task 2
    assert db_session.query(Task).count() == 2 # GATE prep and other_user's task

def test_complete_all_tasks(db_session):
    setup_db(db_session)
    executor = CommandExecutor(db_session, "user1")
    cmd = Command(
        operation=Operation.UPDATE, 
        target_type=TargetType.TASK, 
        scope=Scope.ALL,
        payload={"completed": True}
    )
    
    res = executor.execute([cmd])
    assert res[0].success
    assert res[0].affected_count == 3
    
    # Check that other_user's task was NOT completed
    other = db_session.query(Task).filter_by(user_id="other_user").first()
    assert not other.completed

def test_invalid_target_field(db_session):
    executor = CommandExecutor(db_session, "user1")
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        cmd = Command(
            operation=Operation.UPDATE,
            target_type=TargetType.TASK,
            scope=Scope.ALL,
            payload={"fake_field": True}
        )

def test_failed_transaction_rollback(db_session):
    setup_db(db_session)
    executor = CommandExecutor(db_session, "user1")
    
    # Send a valid command followed by an invalid one in a single multi-command request
    cmd1 = Command(
        operation=Operation.DELETE, 
        target_type=TargetType.TASK, 
        scope=Scope.SINGLE, 
        filters=[CommandFilter(field=FilterField.TITLE, operator=FilterOperator.EQ, value="Task 1")]
    )
    cmd2 = Command(
        operation=Operation.UPDATE,
        target_type=TargetType.TASK,
        scope=Scope.SINGLE,
        filters=[CommandFilter(field=FilterField.TITLE, operator=FilterOperator.EQ, value="Task 1")],
        payload={"title": "test"}
    )
    
    with patch.object(executor, '_get_model', side_effect=[Task, ValueError("Simulated failure")]):
        res = executor.execute([cmd1, cmd2])
        # The whole transaction should fail
        assert len(res) == 1
        assert not res[0].success
    
    # Verify rollback (Task 1 should still exist)
    assert db_session.query(Task).count() == 4
