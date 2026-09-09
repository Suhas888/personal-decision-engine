import pytest
from fastapi import HTTPException
from app.services.validation_service import validate_schedule
from app.models.core import UserProfile, FixedEvent, Task

def test_validate_schedule_success():
    profile = UserProfile(user_id="default_user", sleep_start=1380, sleep_end=420, preferred_start_hour=540, preferred_end_hour=1020)
    
    plan_data = {
        "scheduled_blocks": [
            {"day": "monday", "start_time": 600, "end_time": 720, "duration_minutes": 120, "task_id": 1}
        ],
        "total_scheduled_minutes": 120
    }
    assert validate_schedule(plan_data, profile, [], []) == True

def test_validate_schedule_overlap():
    profile = UserProfile(user_id="default_user", sleep_start=1380, sleep_end=420, preferred_start_hour=540, preferred_end_hour=1020)
    
    plan_data = {
        "scheduled_blocks": [
            {"day": "monday", "start_time": 600, "end_time": 720, "duration_minutes": 120, "task_id": 1},
            {"day": "monday", "start_time": 660, "end_time": 780, "duration_minutes": 120, "task_id": 2}
        ],
        "total_scheduled_minutes": 240
    }
    with pytest.raises(HTTPException) as exc:
        validate_schedule(plan_data, profile, [], [])
    assert "Overlap" in str(exc.value.detail)

def test_validate_schedule_accounting_mismatch():
    profile = UserProfile(user_id="default_user")
    
    plan_data = {
        "scheduled_blocks": [
            {"day": "monday", "start_time": 600, "end_time": 720, "duration_minutes": 120, "task_id": 1}
        ],
        "total_scheduled_minutes": 100 # Mismatch!
    }
    with pytest.raises(HTTPException) as exc:
        validate_schedule(plan_data, profile, [], [])
    assert "Block duration sum" in str(exc.value.detail)
    
def test_validate_schedule_sleep_violation():
    profile = UserProfile(user_id="default_user", sleep_start=1380, sleep_end=420)
    
    plan_data = {
        "scheduled_blocks": [
            {"day": "monday", "start_time": 1400, "end_time": 1420, "duration_minutes": 20, "task_id": 1} # 23:20
        ],
        "total_scheduled_minutes": 20
    }
    with pytest.raises(HTTPException) as exc:
        validate_schedule(plan_data, profile, [], [])
    assert "sleep hours" in str(exc.value.detail)
