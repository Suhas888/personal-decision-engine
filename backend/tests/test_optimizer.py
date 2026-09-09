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
