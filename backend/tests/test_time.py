from datetime import datetime, timezone
import zoneinfo
from app.utils.time_utils import get_current_time, get_relative_day_offset, get_utc_now

def test_get_current_time_default_utc():
    now = get_current_time()
    assert now.tzinfo == timezone.utc

def test_get_current_time_custom_timezone():
    now = get_current_time("Asia/Kolkata")
    assert now.tzinfo == zoneinfo.ZoneInfo("Asia/Kolkata")

def test_get_relative_day_offset():
    # Example: 2026-09-07 is a Monday
    dt = datetime(2026, 9, 7, 10, 0, tzinfo=timezone.utc)
    
    assert get_relative_day_offset(dt, "monday") == 0
    assert get_relative_day_offset(dt, "tuesday") == 1
    assert get_relative_day_offset(dt, "wednesday") == 2
    assert get_relative_day_offset(dt, "thursday") == 3
    assert get_relative_day_offset(dt, "friday") == 4
    assert get_relative_day_offset(dt, "saturday") == 5
    assert get_relative_day_offset(dt, "sunday") == 6
    
    # 2026-09-09 is a Wednesday
    dt = datetime(2026, 9, 9, 10, 0, tzinfo=timezone.utc)
    assert get_relative_day_offset(dt, "wednesday") == 0
    assert get_relative_day_offset(dt, "thursday") == 1
    assert get_relative_day_offset(dt, "tuesday") == 6 # Next Tuesday
    assert get_relative_day_offset(dt, "monday") == 5 # Next Monday
