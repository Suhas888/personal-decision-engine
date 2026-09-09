from app.services.optimization_service import generate_weekly_plan
from app.models.core import UserProfile, Task

def test_block_splitting_accounting_fix():
    # If a task is 45 minutes, max block 30, it should be 2 blocks: 22 and 23 minutes.
    profile = UserProfile(user_id="default_user", max_focus_block_minutes=30, preferred_start_hour=540, preferred_end_hour=1020, timezone="UTC")
    tasks = [
        Task(user_id="default_user", id=1, title="Test", estimated_minutes=45, priority=1, completed=False)
    ]
    
    plan_data = generate_weekly_plan(profile, tasks, [], [])
    blocks = plan_data["scheduled_blocks"]
    assert len(blocks) == 2
    
    # 22 + 23 = 45
    total_dur = sum(b["duration_minutes"] for b in blocks)
    assert total_dur == 45
    assert plan_data["total_scheduled_minutes"] == 45
    assert plan_data["total_requested_minutes"] == 45
    assert plan_data["completion_percentage"] == 100.0
    
def test_completion_percentage_zero_tasks():
    profile = UserProfile(user_id="default_user", max_focus_block_minutes=30, preferred_start_hour=540, preferred_end_hour=1020, timezone="UTC")
    # All tasks completed
    tasks = [
        Task(user_id="default_user", id=1, title="Test", estimated_minutes=45, priority=1, completed=True)
    ]
    
    plan_data = generate_weekly_plan(profile, tasks, [], [])
    
    assert plan_data["total_scheduled_minutes"] == 0
    assert plan_data["total_requested_minutes"] == 0
    # Must be 0.0, not 100.0, per the bugfix
    assert plan_data["completion_percentage"] == 0.0
