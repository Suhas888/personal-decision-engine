from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import List
from ..models.core import FixedEvent, CalendarEvent, ConnectedAccount
from ..schemas.plan import PlanningBlock
from ..utils.time_utils import get_current_time

def get_planning_blocks(db: Session, user_id: str, timezone_str: str) -> List[PlanningBlock]:
    """
    Fetches both manually created FixedEvents and imported CalendarEvents,
    and normalizes them into PlanningBlocks for the optimizer.
    CalendarEvents are mapped to the user's local timezone to calculate day_of_week
    and minutes from midnight.
    """
    blocks: List[PlanningBlock] = []
    
    # 1. Fetch Fixed Events (already normalized as abstract recurring blocks)
    fixed_events = db.query(FixedEvent).filter(FixedEvent.user_id == user_id).all()
    for fe in fixed_events:
        blocks.append(
            PlanningBlock(
                id=f"fe_{fe.id}",
                title=fe.title,
                day_of_week=fe.day_of_week,
                start_time=fe.start_time,
                end_time=fe.end_time,
                is_calendar_event=False
            )
        )
        
    # 2. Fetch Calendar Events (upcoming 7 days)
    # The optimizer plans for a 7 day window starting from 'today' in user_tz
    user_now = get_current_time(timezone_str)
    # Start of today in user tz, converted to UTC
    start_of_today_user = user_now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_window_user = start_of_today_user + timedelta(days=7)
    
    start_utc = start_of_today_user.astimezone(timezone.utc)
    end_utc = end_of_window_user.astimezone(timezone.utc)
    
    # Only fetch events from connected accounts that are confirmed
    calendar_events = db.query(CalendarEvent).join(ConnectedAccount).filter(
        CalendarEvent.user_id == user_id,
        CalendarEvent.status != "cancelled",
        CalendarEvent.end_time >= start_utc,
        CalendarEvent.start_time < end_utc
    ).all()
    
    for ce in calendar_events:
        # Convert UTC event times to User's Timezone
        local_start = ce.start_time.astimezone(start_of_today_user.tzinfo)
        local_end = ce.end_time.astimezone(start_of_today_user.tzinfo)
        
        # If the event spans multiple days, we should technically split it, 
        # but for now we clamp it to the start day's midnight or just represent it.
        # A simple approach:
        day_of_week = local_start.strftime("%A")
        
        start_minutes = local_start.hour * 60 + local_start.minute
        
        # If it crosses midnight, end_minutes could be > 1440
        duration = int((local_end - local_start).total_seconds() / 60)
        end_minutes = start_minutes + duration
        
        blocks.append(
            PlanningBlock(
                id=f"ce_{ce.id}",
                title=ce.title,
                day_of_week=day_of_week,
                start_time=start_minutes,
                end_time=end_minutes,
                is_calendar_event=True
            )
        )
        
    return blocks
