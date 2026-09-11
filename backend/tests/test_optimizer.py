from app.services.optimization_service import generate_weekly_plan
from app.models.core import UserProfile, Task, FixedEvent


def test_optimization_logic():
    profile = UserProfile(user_id="default_user", 
        preferred_start_hour=540,
        preferred_end_hour=1020,
        sleep_start=1380,
        sleep_end=420,
        max_focus_block_minutes=120,
    )

    tasks = [
        Task(user_id="default_user", id=1, title="Test 1", estimated_minutes=240, priority=1, completed=False)
    ]

    events = [
        FixedEvent(user_id="default_user", 
            id=1, title="Fixed 1", day_of_week="Monday", start_time=540, end_time=600
        )
    ]

    plan = generate_weekly_plan(profile, tasks, events)

    assert plan["total_requested_minutes"] == 240
    # Or-tools should schedule at least something if feasible
    assert plan["total_scheduled_minutes"] <= 240
    assert len(plan["scheduled_blocks"]) > 0

def test_optimization_task_splitting():
    profile = UserProfile(user_id="default_user", 
        preferred_start_hour=540,
        preferred_end_hour=1020,
        sleep_start=1380,
        sleep_end=420,
        max_focus_block_minutes=60,
    )

    tasks = [
        Task(user_id="default_user", id=1, title="Test Split", estimated_minutes=130, priority=1, completed=False)
    ]

    plan = generate_weekly_plan(profile, tasks, [])
    
    assert plan["total_scheduled_minutes"] == 130
    blocks = plan["scheduled_blocks"]
    assert len(blocks) == 3
    durations = sorted([b["duration_minutes"] for b in blocks])
    assert durations == [10, 60, 60]

def test_optimization_deadline_enforcement():
    profile = UserProfile(user_id="default_user", 
        preferred_start_hour=540,
        preferred_end_hour=1020,
        sleep_start=1380,
        sleep_end=420,
        max_focus_block_minutes=60,
    )

    # If task needs 500 hours before yesterday, it should be unscheduled
    from datetime import datetime, timedelta
    from app.utils.time_utils import get_current_time
    yesterday = (get_current_time("UTC") - timedelta(days=1)).strftime("%Y-%m-%d")

    tasks = [
        Task(user_id="default_user", id=1, title="Impossible Task", estimated_minutes=60, priority=1, completed=False, deadline=yesterday)
    ]

    plan = generate_weekly_plan(profile, tasks, [])
    
    assert plan["total_scheduled_minutes"] == 0
    assert len(plan["unscheduled_tasks"]) == 1

def test_optimization_day_bleed():
    profile = UserProfile(user_id="default_user", 
        preferred_start_hour=1380, # 23:00
        preferred_end_hour=1440,   # 24:00 (end of day)
        sleep_start=1440,
        sleep_end=420,
        max_focus_block_minutes=120,
    )

    tasks = [
        Task(user_id="default_user", id=1, title="Bleed Task", estimated_minutes=120, priority=1, completed=False)
    ]

    plan = generate_weekly_plan(profile, tasks, [])
    # Since only 60 mins are available on any given day, a 120 min block cannot be scheduled entirely on one day
    # With max_focus_block=120, it tries to schedule a 120 min block.
    # It must fail or split into smaller blocks if we change max_focus_block.
    # But here, since we enforce end_var <= day_offset + 1440, a 120 min block starting at 1380 would end at 1500 > 1440.
    # Thus, it cannot be scheduled.
    
    assert len(plan["scheduled_blocks"]) == 0
