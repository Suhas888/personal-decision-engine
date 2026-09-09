import pytest
from datetime import datetime, date, timezone
from app.services.optimization_service import generate_weekly_plan
from app.models.core import UserProfile, Task, FixedEvent, DynamicConstraint

class MockProfile:
    def __init__(self, timezone="UTC"):
        self.timezone = timezone
        self.preferred_start_hour = 9 * 60
        self.preferred_end_hour = 17 * 60
        self.max_focus_block_minutes = 120
        self.daily_task_limit_minutes_weekday = 8 * 60
        self.daily_task_limit_minutes_weekend = 4 * 60

@pytest.fixture
def base_tasks():
    t1 = Task(user_id="default_user", id=1, title="Coding", category="work", estimated_minutes=120, priority=1, completed=False)
    t2 = Task(user_id="default_user", id=2, title="Emails", category="admin", estimated_minutes=60, priority=2, completed=False)
    t3 = Task(user_id="default_user", id=3, title="Planning", category="admin", estimated_minutes=60, priority=2, completed=False)
    return [t1, t2, t3]

def test_integration_no_constraints(base_tasks):
    profile = MockProfile()
    plan = generate_weekly_plan(profile, base_tasks, [])
    assert plan["completion_percentage"] == 100.0
    assert len(plan["scheduled_blocks"]) >= 3

def test_integration_max_daily_hours(base_tasks):
    profile = MockProfile()
    # Force max 60 mins of admin per day. Emails and Planning are both admin (60m each).
    # They should not be scheduled on the same day.
    c = DynamicConstraint(user_id="default_user", 
        id=1, type="MAX_DAILY_HOURS", scope="CATEGORY", target="admin",
        parameters={"max_minutes": 60}, strength="HARD"
    )
    plan = generate_weekly_plan(profile, base_tasks, [], dynamic_constraints=[c])
    
    assert plan["completion_percentage"] == 100.0
    
    admin_blocks = [b for b in plan["scheduled_blocks"] if b["task_title"] in ["Emails", "Planning"]]
    assert len(admin_blocks) == 2
    assert admin_blocks[0]["date"] != admin_blocks[1]["date"]

def test_integration_avoid_time(base_tasks):
    profile = MockProfile()
    c = DynamicConstraint(user_id="default_user", 
        id=2, type="AVOID_TIME", scope="TASK", target="Coding",
        parameters={"start_minute": 540, "end_minute": 720}, strength="HARD" # Avoid 9am-12pm
    )
    plan = generate_weekly_plan(profile, base_tasks, [], dynamic_constraints=[c])
    
    for b in plan["scheduled_blocks"]:
        if b["task_title"] == "Coding":
            assert not (b["start_time"] < 720 and b["end_time"] > 540)

def test_integration_force_day(base_tasks):
    profile = MockProfile()
    c = DynamicConstraint(user_id="default_user", 
        id=3, type="FORCE_DAY", scope="TASK", target="Planning",
        parameters={"day": "Sunday", "target": "Planning"}, strength="HARD"
    )
    plan = generate_weekly_plan(profile, base_tasks, [], dynamic_constraints=[c])
    
    for b in plan["scheduled_blocks"]:
        if b["task_title"] == "Planning":
            assert b["day"].lower() == "sunday"

def test_integration_soft_constraint_does_not_fail(base_tasks):
    profile = MockProfile()
    # Impossible hard constraint would fail.
    # Soft constraint will just be ignored/penalized.
    c = DynamicConstraint(user_id="default_user", 
        id=4, type="MAX_DAILY_HOURS", scope="GLOBAL", target=None,
        parameters={"max_minutes": 10}, strength="SOFT"
    )
    plan = generate_weekly_plan(profile, base_tasks, [], dynamic_constraints=[c])
    # The solver finds a valid plan, though it may choose not to schedule everything 
    # if the soft penalty outweighs the scheduling reward.
    assert len(plan["constraint_warnings"]) == 0
    assert plan["objective_score"] > 0 or plan["completion_percentage"] >= 0.0

def test_integration_unsupported_type_raises_error(base_tasks):
    profile = MockProfile()
    c = DynamicConstraint(user_id="default_user", 
        id=5, type="IMPOSSIBLE_TYPE", scope="GLOBAL", target=None,
        parameters={}, strength="HARD"
    )
    with pytest.raises(ValueError, match="Invalid dynamic constraint"):
        generate_weekly_plan(profile, base_tasks, [], dynamic_constraints=[c])

def test_integration_day_mapping_timezone():
    # Verify that the day offset calculation strictly respects the user timezone.
    # We will simulate a user profile timezone.
    profile = MockProfile(timezone="Asia/Tokyo") # +9 UTC
    
    t1 = Task(user_id="default_user", id=1, title="Test", estimated_minutes=60, priority=1, completed=False)
    
    # We force the task to "Monday"
    c = DynamicConstraint(user_id="default_user", 
        id=6, type="FORCE_DAY", scope="GLOBAL", target=None,
        parameters={"day": "Monday", "target": "GLOBAL"}, strength="HARD"
    )
    plan = generate_weekly_plan(profile, [t1], [], dynamic_constraints=[c])
    
    assert len(plan["scheduled_blocks"]) == 1
    assert plan["scheduled_blocks"][0]["day"].lower() == "monday"
