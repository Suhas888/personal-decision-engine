from typing import Dict, Any, List
from fastapi import HTTPException
from ..models.core import UserProfile, FixedEvent, Task
from ..utils.time_utils import get_current_time, get_relative_day_offset

def validate_schedule(plan_data: Dict[str, Any], profile: UserProfile, fixed_events: List[FixedEvent], tasks: List[Task]):
    blocks = plan_data.get("scheduled_blocks", [])
    
    # 1. Total minutes accounting validation
    calc_sum = sum(b.get("duration_minutes", 0) for b in blocks if b.get("task_id") is not None)
    total_scheduled = plan_data.get("total_scheduled_minutes", 0)
    if calc_sum != total_scheduled:
        raise HTTPException(
            status_code=500, 
            detail=f"Validation Error: Block duration sum ({calc_sum}) does not match total scheduled ({total_scheduled})"
        )
    
    # 2. Extract specific daily bounds from profile (in minutes from midnight)
    pref_start = profile.preferred_start_hour if profile.preferred_start_hour is not None else 540 # 9am
    pref_end = profile.preferred_end_hour if profile.preferred_end_hour is not None else 1020 # 5pm
    sleep_start = profile.sleep_start if profile.sleep_start is not None else 1380 # 11pm
    sleep_end = profile.sleep_end if profile.sleep_end is not None else 420 # 7am

    # Process all blocks to absolute minutes from a week start to check overlaps
    # Convert day strings back to indices for absolute checking
    day_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
    
    user_tz = getattr(profile, "timezone", "UTC")
    today_dt = get_current_time(user_tz)
    
    # Rebuild fixed event absolute intervals
    all_intervals = []
    
    for event in fixed_events:
        day_idx = get_relative_day_offset(today_dt, event.day_of_week)
        day_offset = day_idx * 24 * 60
        start = day_offset + int(event.start_time)
        end = day_offset + int(event.end_time)
        all_intervals.append({"start": start, "end": end, "type": "fixed", "id": event.id})
        
    for b in blocks:
        # Rebuild relative block absolute intervals
        # Since 'day' in blocks is the exact string name, we can find its relative offset
        day_idx = get_relative_day_offset(today_dt, b["day"])
        day_offset = day_idx * 24 * 60
        start = day_offset + b["start_time"]
        end = day_offset + b["end_time"]
        all_intervals.append({"start": start, "end": end, "type": "task", "id": b["task_id"]})
        
        # Check against daily bounds if it's a task block
        if b["start_time"] < pref_start or b["end_time"] > pref_end:
            # Depending on how flexible the bounds are, we might just warn, but prompt said "no sleep violation"
            # We strictly check against sleep hours.
            # Sleep hours: if sleep_end < sleep_start, it crosses midnight.
            # E.g. sleep_start = 23:00 (1380), sleep_end = 07:00 (420)
            st = b["start_time"]
            en = b["end_time"]
            
            # Check if block falls inside sleep window
            if sleep_start > sleep_end:
                if (st >= sleep_start or st < sleep_end) or (en > sleep_start or en <= sleep_end):
                    raise HTTPException(status_code=500, detail="Validation Error: Task scheduled during sleep hours")
            else:
                if (st >= sleep_start and st < sleep_end) or (en > sleep_start and en <= sleep_end):
                    raise HTTPException(status_code=500, detail="Validation Error: Task scheduled during sleep hours")
            
    # 3. Check for Overlaps
    # Sort all intervals by start time
    all_intervals.sort(key=lambda x: x["start"])
    for i in range(len(all_intervals) - 1):
        if all_intervals[i]["end"] > all_intervals[i+1]["start"]:
            raise HTTPException(
                status_code=500, 
                detail=f"Validation Error: Overlap detected between {all_intervals[i]['type']} and {all_intervals[i+1]['type']}"
            )
            
    # If we got here, plan is mathematically sound.
    return True
