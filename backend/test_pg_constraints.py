import sys
import os
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from app.config import settings
from app.models.core import User, Preference, Task, ScheduleBlock, Plan, PlanHistory
from sqlalchemy.exc import IntegrityError, OperationalError

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def run_tests():
    db = SessionLocal()
    try:
        print("=== TEST 1: Unique Preference ===")
        user_a = User(id="user_A", email="a@test.com", hashed_password="pw")
        user_b = User(id="user_B", email="b@test.com", hashed_password="pw")
        db.add_all([user_a, user_b])
        db.commit()

        # Create Preference(A, 'x') and Preference(B, 'x')
        db.add(Preference(user_id="user_A", key="x", value="1"))
        db.add(Preference(user_id="user_B", key="x", value="2"))
        db.commit()
        print("Test 1a passed: Created overlapping keys for different users")

        try:
            # Attempt Preference(A, 'x') again
            db.add(Preference(user_id="user_A", key="x", value="3"))
            db.commit()
            print("Test 1b FAILED: Allowed duplicate key for same user")
        except IntegrityError:
            db.rollback()
            print("Test 1b passed: IntegrityError raised for duplicate user/key")

        print("\n=== TEST 2: FK Violation ===")
        try:
            db.add(Task(user_id="nonexistent_user", title="Task", priority=1))
            db.commit()
            print("Test 2 FAILED: Allowed task with nonexistent user")
        except IntegrityError:
            db.rollback()
            print("Test 2 passed: IntegrityError raised for missing FK")

        print("\n=== TEST 3: ON DELETE SET NULL for task ===")
        plan = Plan(id=99, user_id="user_A", week_start="2026")
        task = Task(id=99, user_id="user_A", title="Test Task", priority=1)
        db.add_all([plan, task])
        db.commit()
        
        block = ScheduleBlock(id=99, user_id="user_A", plan_id=99, task_id=99, block_type="focus")
        db.add(block)
        db.commit()

        # Delete Task
        db.delete(task)
        db.commit()
        db.expire_all()
        
        b = db.query(ScheduleBlock).filter(ScheduleBlock.id==99).first()
        if b and b.task_id is None:
            print("Test 3 passed: ScheduleBlock remained, task_id became NULL")
        else:
            print("Test 3 FAILED: block missing or task_id not null")

        print("\n=== TEST 4: ON DELETE CASCADE for user ===")
        db.delete(user_a)
        db.commit()
        
        # Verify user_A records deleted
        plans = db.query(Plan).filter(Plan.user_id=="user_A").count()
        prefs = db.query(Preference).filter(Preference.user_id=="user_A").count()
        blocks = db.query(ScheduleBlock).filter(ScheduleBlock.user_id=="user_A").count()
        if plans == 0 and prefs == 0 and blocks == 0:
            print("Test 4 passed: All user_A records cascaded delete")
        else:
            print(f"Test 4 FAILED: plans={plans}, prefs={prefs}, blocks={blocks}")

        print("\n=== TEST 5: ON DELETE SET NULL for plan history ===")
        plan_old = Plan(id=101, user_id="user_B", week_start="2026")
        db.add(plan_old)
        db.commit()

        history = PlanHistory(id=101, user_id="user_B", previous_plan_id=101, new_plan_id=None)
        db.add(history)
        db.commit()

        db.delete(plan_old)
        db.commit()
        db.expire_all()

        h = db.query(PlanHistory).filter(PlanHistory.id==101).first()
        if h and h.previous_plan_id is None:
            print("Test 5 passed: PlanHistory remained, previous_plan_id became NULL")
        else:
            print("Test 5 FAILED: history missing or previous_plan_id not null")

    finally:
        db.close()

if __name__ == "__main__":
    run_tests()
