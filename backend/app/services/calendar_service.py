import httpx
from datetime import datetime, timezone, timedelta
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..config import settings
from ..models.core import ConnectedAccount, CalendarEvent
from ..utils.encryption_utils import encrypt_string, decrypt_string
import uuid

# Google OAuth Constants
GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
# We only request read-only access to calendar events
GOOGLE_SCOPES = "https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/userinfo.email"

class CalendarAPIError(Exception):
    pass

class OAuthStateError(Exception):
    pass

async def get_google_auth_url(user_id: str) -> Tuple[str, str]:
    """Generates the OAuth URL and a state token to prevent CSRF."""
    state = str(uuid.uuid4())
    backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
    redirect_uri = f"{backend_url}/api/calendar/auth/google/callback"

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "consent",  # Force consent to ensure we get a refresh token
        "state": state
    }
    
    query = "&".join([f"{k}={v}" for k, v in params.items()])
    url = f"{GOOGLE_AUTHORIZATION_URL}?{query}"
    return url, state


async def exchange_google_code(code: str, db: Session, user_id: str) -> ConnectedAccount:
    """Exchanges an authorization code for tokens, fetches user email, and saves the connected account."""
    backend_url = getattr(settings, "BACKEND_URL", "http://localhost:8000")
    redirect_uri = f"{backend_url}/api/calendar/auth/google/callback"
    
    async with httpx.AsyncClient() as client:
        # 1. Exchange code
        token_res = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri
        })
        
        if token_res.status_code != 200:
            raise CalendarAPIError(f"Failed to exchange token: {token_res.text}")
            
        token_data = token_res.json()
        access_token = token_data["access_token"]
        refresh_token = token_data.get("refresh_token") # May be missing if not prompt=consent
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        # 2. Fetch user profile (email)
        userinfo_res = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        if userinfo_res.status_code != 200:
            raise CalendarAPIError("Failed to fetch user email")
            
        email = userinfo_res.json().get("email", "unknown_email")
        
        # 3. Save to database
        account = db.query(ConnectedAccount).filter(
            ConnectedAccount.user_id == user_id, 
            ConnectedAccount.provider == "google"
        ).first()
        
        if not account:
            account = ConnectedAccount(
                user_id=user_id,
                provider="google",
                provider_account_id=email
            )
            db.add(account)
            
        account.access_token_encrypted = encrypt_string(access_token)
        if refresh_token:
            account.refresh_token_encrypted = encrypt_string(refresh_token)
        account.expires_at = expires_at
        account.provider_account_id = email
        
        db.commit()
        db.refresh(account)
        return account


async def refresh_google_token_if_needed(account: ConnectedAccount, db: Session) -> str:
    """Refreshes the access token if it's expired or about to expire within 5 minutes."""
    # Ensure expires_at is timezone-aware
    expires_at = account.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if expires_at > datetime.now(timezone.utc) + timedelta(minutes=5):
        return decrypt_string(account.access_token_encrypted)
        
    if not account.refresh_token_encrypted:
        raise CalendarAPIError("No refresh token available to renew access.")
        
    refresh_token = decrypt_string(account.refresh_token_encrypted)
    
    async with httpx.AsyncClient() as client:
        res = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token"
        })
        
        if res.status_code != 200:
            raise CalendarAPIError(f"Failed to refresh token: {res.text}")
            
        token_data = res.json()
        new_access_token = token_data["access_token"]
        expires_in = token_data.get("expires_in", 3600)
        
        account.access_token_encrypted = encrypt_string(new_access_token)
        account.expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
        
        db.commit()
        return new_access_token


async def sync_calendar_events(user_id: str, db: Session) -> Dict[str, Any]:
    """Syncs events from Google Calendar for the connected account."""
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == user_id, 
        ConnectedAccount.provider == "google"
    ).first()
    
    if not account:
        raise ValueError("No connected Google account found.")
        
    access_token = await refresh_google_token_if_needed(account, db)
    
    async with httpx.AsyncClient() as client:
        url = f"{GOOGLE_CALENDAR_API_BASE}/calendars/primary/events"
        params = {
            "singleEvents": "true",       # Expands recurring events into single instances
            "maxResults": 1000,
        }
        
        if account.sync_token:
            params["syncToken"] = account.sync_token
        else:
            # First time sync: just fetch from 1 week ago up to 4 weeks in the future to keep it light
            now = datetime.now(timezone.utc)
            time_min = (now - timedelta(days=7)).isoformat()
            time_max = (now + timedelta(days=30)).isoformat()
            params["timeMin"] = time_min
            params["timeMax"] = time_max
            
        headers = {"Authorization": f"Bearer {access_token}"}
        
        synced_count = 0
        deleted_count = 0
        
        while True:
            res = await client.get(url, params=params, headers=headers)
            
            if res.status_code == 410: # syncToken is invalidated by Google
                account.sync_token = None
                db.commit()
                # Recurse once without sync_token
                return await sync_calendar_events(user_id, db)
                
            if res.status_code != 200:
                raise CalendarAPIError(f"Google Calendar API Error: {res.text}")
                
            data = res.json()
            items = data.get("items", [])
            
            for item in items:
                external_id = item["id"]
                status = item.get("status", "confirmed")
                
                existing = db.query(CalendarEvent).filter(
                    CalendarEvent.account_id == account.id,
                    CalendarEvent.external_event_id == external_id
                ).first()
                
                if status == "cancelled":
                    if existing:
                        db.delete(existing)
                        deleted_count += 1
                    continue
                    
                # Parse times
                start_obj = item.get("start", {})
                end_obj = item.get("end", {})
                
                # Handling all-day events vs datetime events
                all_day = "date" in start_obj
                
                if all_day:
                    # 'date' format is YYYY-MM-DD
                    start_str = start_obj["date"] + "T00:00:00Z"
                    end_str = end_obj["date"] + "T00:00:00Z"
                else:
                    start_str = start_obj.get("dateTime")
                    end_str = end_obj.get("dateTime")
                    
                if not start_str or not end_str:
                    continue # Skip invalid events
                    
                start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                
                if not existing:
                    existing = CalendarEvent(
                        user_id=user_id,
                        account_id=account.id,
                        external_event_id=external_id
                    )
                    db.add(existing)
                    
                existing.title = item.get("summary", "Untitled Event")
                existing.start_time = start_time
                existing.end_time = end_time
                existing.all_day = all_day
                existing.recurring_event_id = item.get("recurringEventId")
                existing.status = status
                synced_count += 1
                
            next_page_token = data.get("nextPageToken")
            if next_page_token:
                params["pageToken"] = next_page_token
                if "syncToken" in params:
                    del params["syncToken"]
                if "timeMin" in params:
                    del params["timeMin"]
                if "timeMax" in params:
                    del params["timeMax"]
            else:
                next_sync_token = data.get("nextSyncToken")
                if next_sync_token:
                    account.sync_token = next_sync_token
                break
                
        account.last_sync_at = datetime.now(timezone.utc)
        db.commit()
        
        return {
            "synced_count": synced_count,
            "deleted_count": deleted_count,
            "last_sync_at": account.last_sync_at.isoformat()
        }
