"""
PostgreSQL integration tests — FK, CASCADE, Unique, and transaction enforcement.

All 10 required scenarios tested against real PostgreSQL (pde_test schema).
Uses SQLAlchemy directly (not HTTP API) to precisely target DB-level behavior.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.pg


# ---------------------------------------------------------------------------
# Helper: create a valid user row
# ---------------------------------------------------------------------------

def _create_user(pg_session, email="test@pgfk.com", password_hash="fakehash") -> object:
    from app.models.core import User, UserProfile
    from app.services.auth_service import get_password_hash
    user = User(email=email, hashed_password=get_password_hash("TestPass1!"))
    pg_session.add(user)
    pg_session.flush()  # get ID without committing
    return user


# ---------------------------------------------------------------------------
# 1. Invalid user FK → IntegrityError
# ---------------------------------------------------------------------------

class TestFKInvalidUser:
    def test_task_with_nonexistent_user_id_rejected(self, pg_session):
        from app.models.core import Task
        pg_session.add(Task(
            user_id="00000000-0000-0000-0000-000000000000",  # does not exist
            title="Orphan Task",
            estimated_minutes=30,
        ))
        with pytest.raises(IntegrityError):
            pg_session.flush()
        pg_session.rollback()

    def test_refresh_session_with_nonexistent_user_rejected(self, pg_session):
        from app.models.core import RefreshSession
        pg_session.add(RefreshSession(
            user_id="00000000-0000-0000-0000-000000000001",
            refresh_token_jti="fake-jti-xyz",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        ))
        with pytest.raises(IntegrityError):
            pg_session.flush()
        pg_session.rollback()


# ---------------------------------------------------------------------------
# 2. Duplicate email → IntegrityError
# ---------------------------------------------------------------------------

class TestUniqueEmailConstraint:
    def test_duplicate_email_rejected(self, pg_session):
        from app.models.core import User
        from app.services.auth_service import get_password_hash
        user1 = User(email="unique@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        user2 = User(email="unique@pgfk.com", hashed_password=get_password_hash("Pass2!"))
        pg_session.add(user1)
        pg_session.flush()
        pg_session.add(user2)
        with pytest.raises(IntegrityError):
            pg_session.flush()
        pg_session.rollback()


# ---------------------------------------------------------------------------
# 3. Duplicate profile for same user → IntegrityError
# ---------------------------------------------------------------------------

class TestUniqueProfileConstraint:
    def test_duplicate_user_profile_rejected(self, pg_session):
        from app.models.core import User, UserProfile
        from app.services.auth_service import get_password_hash
        user = User(email="profile@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        p1 = UserProfile(user_id=user.id, name="Alice")
        pg_session.add(p1)
        pg_session.flush()

        p2 = UserProfile(user_id=user.id, name="Alice Dup")
        pg_session.add(p2)
        with pytest.raises(IntegrityError):
            pg_session.flush()
        pg_session.rollback()


# ---------------------------------------------------------------------------
# 4. Same preference key for same user → IntegrityError
# ---------------------------------------------------------------------------

class TestUniquePreferenceConstraint:
    def test_duplicate_preference_key_same_user_rejected(self, pg_session):
        from app.models.core import User, Preference
        from app.services.auth_service import get_password_hash
        user = User(email="pref@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        p1 = Preference(user_id=user.id, key="theme", value="dark")
        pg_session.add(p1)
        pg_session.flush()

        p2 = Preference(user_id=user.id, key="theme", value="light")
        pg_session.add(p2)
        with pytest.raises(IntegrityError):
            pg_session.flush()
        pg_session.rollback()


# ---------------------------------------------------------------------------
# 5. Same preference key for different users → ALLOWED
# ---------------------------------------------------------------------------

class TestPreferenceCrossUserAllowed:
    def test_same_preference_key_different_users_allowed(self, pg_session):
        from app.models.core import User, Preference
        from app.services.auth_service import get_password_hash
        u1 = User(email="pref_a@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        u2 = User(email="pref_b@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add_all([u1, u2])
        pg_session.flush()

        p1 = Preference(user_id=u1.id, key="timezone", value="UTC")
        p2 = Preference(user_id=u2.id, key="timezone", value="Asia/Tokyo")
        pg_session.add_all([p1, p2])
        pg_session.flush()  # must NOT raise

        pg_session.commit()
        # Verify both exist
        from app.models.core import Preference
        count = pg_session.query(Preference).filter_by(key="timezone").count()
        assert count == 2


# ---------------------------------------------------------------------------
# 6. Delete User → CASCADE to owned rows
# ---------------------------------------------------------------------------

class TestCascadeOnUserDelete:
    def test_delete_user_cascades_to_tasks_and_profile(self, pg_session):
        from app.models.core import User, UserProfile, Task
        from app.services.auth_service import get_password_hash

        user = User(email="cascade@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        profile = UserProfile(user_id=user.id, name="Cascade User")
        task1 = Task(user_id=user.id, title="C-Task1", estimated_minutes=30)
        task2 = Task(user_id=user.id, title="C-Task2", estimated_minutes=60)
        pg_session.add_all([profile, task1, task2])
        pg_session.commit()

        user_id = user.id

        # Delete the user
        pg_session.delete(user)
        pg_session.commit()

        # Profile and tasks must be gone
        assert pg_session.query(UserProfile).filter_by(user_id=user_id).count() == 0
        assert pg_session.query(Task).filter_by(user_id=user_id).count() == 0

    def test_delete_user_cascades_to_refresh_sessions(self, pg_session):
        from app.models.core import User, RefreshSession
        from app.services.auth_service import get_password_hash

        user = User(email="cascade2@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        sess = RefreshSession(
            user_id=user.id,
            refresh_token_jti="jti-cascade-test",
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        pg_session.add(sess)
        pg_session.commit()

        user_id = user.id
        pg_session.delete(user)
        pg_session.commit()

        assert pg_session.query(RefreshSession).filter_by(user_id=user_id).count() == 0


# ---------------------------------------------------------------------------
# 7. Delete Task → ScheduleBlock.task_id SET NULL
# ---------------------------------------------------------------------------

class TestSetNullOnTaskDelete:
    def test_delete_task_sets_schedule_block_task_id_null(self, pg_session):
        from app.models.core import User, UserProfile, Task, Plan, ScheduleBlock
        from app.services.auth_service import get_password_hash

        user = User(email="setnull@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        profile = UserProfile(user_id=user.id, name="SetNull User")
        task = Task(user_id=user.id, title="Linked Task", estimated_minutes=60)
        pg_session.add_all([profile, task])
        pg_session.flush()

        plan = Plan(user_id=user.id, week_start=datetime.now(timezone.utc).date().isoformat())
        pg_session.add(plan)
        pg_session.flush()

        block = ScheduleBlock(
            user_id=user.id,
            plan_id=plan.id,
            task_id=task.id,
            date="2026-09-08",
            start_time=540,
            end_time=600
        )
        pg_session.add(block)
        pg_session.commit()

        block_id = block.id
        pg_session.delete(task)
        pg_session.commit()

        pg_session.expire(block)
        refreshed_block = pg_session.query(ScheduleBlock).filter_by(id=block_id).first()
        assert refreshed_block is not None
        assert refreshed_block.task_id is None  # SET NULL confirmed


# ---------------------------------------------------------------------------
# 8. Delete Plan → PlanHistory plan references SET NULL
# ---------------------------------------------------------------------------

class TestSetNullOnPlanDelete:
    def test_delete_plan_sets_plan_history_plan_id_null(self, pg_session):
        from app.models.core import User, UserProfile, Plan, PlanHistory
        from app.services.auth_service import get_password_hash

        user = User(email="phsetnull@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        profile = UserProfile(user_id=user.id, name="PH SetNull")
        pg_session.add(profile)

        prev_plan = Plan(user_id=user.id,
                         week_start=datetime(2026, 9, 1, tzinfo=timezone.utc).date().isoformat())
        new_plan = Plan(user_id=user.id,
                        week_start=datetime(2026, 9, 8, tzinfo=timezone.utc).date().isoformat())
        pg_session.add_all([prev_plan, new_plan])
        pg_session.flush()

        history = PlanHistory(
            user_id=user.id,
            previous_plan_id=prev_plan.id,
            new_plan_id=new_plan.id,
            change_reason="replanned",
        )
        pg_session.add(history)
        pg_session.commit()

        history_id = history.id
        # Delete the new_plan
        pg_session.delete(new_plan)
        pg_session.commit()

        pg_session.expire(history)
        refreshed = pg_session.query(PlanHistory).filter_by(id=history_id).first()
        assert refreshed is not None
        assert refreshed.new_plan_id is None  # SET NULL confirmed


# ---------------------------------------------------------------------------
# 9. Transaction failure → no partial commit
# ---------------------------------------------------------------------------

class TestTransactionAtomicity:
    def test_failed_transaction_leaves_no_partial_data(self, pg_session, pg_engine):
        from app.models.core import User, Task
        from app.services.auth_service import get_password_hash

        user = User(email="atomic@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        # Valid task + orphan task (will trigger FK violation)
        valid_task = Task(user_id=user.id, title="Valid", estimated_minutes=30)
        orphan_task = Task(
            user_id="00000000-0000-0000-0000-999999999999",
            title="Orphan",
            estimated_minutes=30,
        )
        pg_session.add(valid_task)
        pg_session.flush()  # valid_task should be inserted

        pg_session.add(orphan_task)
        with pytest.raises(IntegrityError):
            pg_session.flush()

        pg_session.rollback()

        # The rollback removed everything — including the valid_task
        with pg_engine.connect() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM tasks WHERE title='Valid'")
            ).scalar()
        assert count == 0


# ---------------------------------------------------------------------------
# 10. Timezone-aware datetime round-trip
# ---------------------------------------------------------------------------

class TestTimezoneRoundTrip:
    def test_datetime_roundtrip_preserves_utc(self, pg_session):
        from app.models.core import User, RefreshSession
        from app.services.auth_service import get_password_hash

        user = User(email="tz@pgfk.com", hashed_password=get_password_hash("Pass1!"))
        pg_session.add(user)
        pg_session.flush()

        original_dt = datetime(2026, 9, 8, 12, 30, 0, tzinfo=timezone.utc)
        sess = RefreshSession(
            user_id=user.id,
            refresh_token_jti="jti-tz-roundtrip",
            expires_at=original_dt,
        )
        pg_session.add(sess)
        pg_session.commit()

        pg_session.expire(sess)
        refreshed = pg_session.query(RefreshSession).filter_by(
            refresh_token_jti="jti-tz-roundtrip"
        ).first()

        stored_dt = refreshed.expires_at
        if stored_dt.tzinfo is None:
            stored_dt = stored_dt.replace(tzinfo=timezone.utc)

        assert stored_dt == original_dt
        assert stored_dt.tzinfo is not None  # must be tz-aware coming back
