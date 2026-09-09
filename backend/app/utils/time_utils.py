from datetime import datetime, timezone, timedelta
import zoneinfo
from typing import Tuple

def get_current_time(tz_string: str = "UTC") -> datetime:
    """Returns the current timezone-aware datetime for the given user timezone."""
    if not tz_string or tz_string.upper() == "UTC":
        return datetime.now(timezone.utc)
    try:
        tz = zoneinfo.ZoneInfo(tz_string)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz)

def get_relative_day_offset(start_date: datetime, target_day_name: str) -> int:
    """
    Given a starting date and a target day of the week (e.g., 'monday'), 
    returns the offset in days from the start_date to the NEXT occurrence of that day 
    (or 0 if it's the same day).
    """
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    target_idx = days.index(target_day_name.lower())
    start_idx = start_date.weekday()
    
    diff = (target_idx - start_idx) % 7
    return diff

def get_utc_now() -> datetime:
    """Returns the current UTC time, properly timezone-aware."""
    return datetime.now(timezone.utc)
