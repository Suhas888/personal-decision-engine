import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.models.core import User, ConnectedAccount, CalendarEvent

def test_calendar_event_db_lifecycle(pg_session: Session, pg_user_a):
    user_id = pg_user_a["id"]
    
    # 1. Connect Google Account
    account = ConnectedAccount(
        user_id=user_id,
        provider="google",
        provider_account_id="test@example.com",
        access_token_encrypted="fake_access",
        refresh_token_encrypted="fake_refresh",
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    pg_session.add(account)
    pg_session.commit()
    
    assert account.id is not None
    
    # 2. Add Calendar Event
    start_time = datetime.now(timezone.utc)
    end_time = start_time + timedelta(hours=1)
    
    event = CalendarEvent(
        user_id=user_id,
        account_id=account.id,
        external_event_id="google_event_123",
        title="Team Sync",
        start_time=start_time,
        end_time=end_time
    )
    pg_session.add(event)
    pg_session.commit()
    
    assert event.id is not None
    
    # 3. Test uniqueness constraint
    duplicate = CalendarEvent(
        user_id=user_id,
        account_id=account.id,
        external_event_id="google_event_123",
        title="Duplicate",
        start_time=start_time,
        end_time=end_time
    )
    pg_session.add(duplicate)
    
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        pg_session.commit()
        
    pg_session.rollback()
    
    # 4. Test Cascade Delete
    event_id = event.id
    pg_session.delete(account)
    pg_session.commit()
    
    deleted_event = pg_session.query(CalendarEvent).filter_by(id=event_id).first()
    assert deleted_event is None
