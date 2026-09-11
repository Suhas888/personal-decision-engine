from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from typing import Dict, Any

from ...database.core import get_db
from ...models.core import User, ConnectedAccount, CalendarEvent
from ..dependencies import get_current_user
from ...services.calendar_service import (
    get_google_auth_url,
    exchange_google_code,
    sync_calendar_events,
    CalendarAPIError
)
from ...config import settings

router = APIRouter()

@router.get("/auth/google")
async def connect_google_calendar(request: Request, current_user: User = Depends(get_current_user)):
    """Starts the Google OAuth flow."""
    url, state = await get_google_auth_url(current_user.id)
    # Store state in cookie to prevent CSRF
    response = RedirectResponse(url=url)
    response.set_cookie(key="oauth_state", value=state, httponly=True, max_age=300, secure=True, samesite="lax")
    return response

@router.get("/auth/google/callback")
async def google_auth_callback(request: Request, db: Session = Depends(get_db)):
    """Handles the Google OAuth callback."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    error = request.query_params.get("error")
    
    frontend_redirect = f"{settings.FRONTEND_URL}/settings"
    
    if error:
        return RedirectResponse(url=f"{frontend_redirect}?error=oauth_rejected")
        
    if not code or not state:
        return RedirectResponse(url=f"{frontend_redirect}?error=missing_params")
        
    expected_state = request.cookies.get("oauth_state")
    if not expected_state or expected_state != state:
        return RedirectResponse(url=f"{frontend_redirect}?error=invalid_state")
        
    # We don't have current_user here directly because it's a cross-origin redirect from Google,
    # so standard Authorization headers won't be present. We need to rely on the session cookie
    # or pass a JWT token in the state. Wait, our auth uses cookies! So `get_current_user` can read the `pde_access_token` cookie!
    # Let's manually invoke get_current_user.
    try:
        current_user = get_current_user(request, db)
    except HTTPException:
        return RedirectResponse(url=f"{settings.FRONTEND_URL}/login?error=auth_required_for_calendar")
        
    try:
        await exchange_google_code(code, db, current_user.id)
        # Immediately trigger an initial sync
        await sync_calendar_events(current_user.id, db)
        
        response = RedirectResponse(url=f"{frontend_redirect}?success=calendar_connected")
        response.delete_cookie("oauth_state")
        return response
    except Exception as e:
        print(f"OAuth callback error: {str(e)}")
        response = RedirectResponse(url=f"{frontend_redirect}?error=exchange_failed")
        response.delete_cookie("oauth_state")
        return response

@router.get("/status")
def get_calendar_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Returns the current calendar integration status."""
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == current_user.id,
        ConnectedAccount.provider == "google"
    ).first()
    
    if not account:
        return {"isConnected": False}
        
    return {
        "isConnected": True,
        "provider": account.provider,
        "providerEmail": account.provider_account_id,
        "lastSyncedAt": account.last_sync_at.isoformat() if account.last_sync_at else None
    }

@router.post("/sync")
async def sync_calendar(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Manually triggers a calendar sync."""
    try:
        result = await sync_calendar_events(current_user.id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CalendarAPIError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error during sync")

@router.delete("/disconnect")
def disconnect_calendar(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Disconnects the calendar and removes all imported events."""
    account = db.query(ConnectedAccount).filter(
        ConnectedAccount.user_id == current_user.id,
        ConnectedAccount.provider == "google"
    ).first()
    
    if not account:
        raise HTTPException(status_code=404, detail="No connected account found")
        
    db.delete(account)
    db.commit()
    
    return {"status": "success", "detail": "Calendar disconnected and events removed."}
