from fastapi import APIRouter, Depends, HTTPException, Response, Request, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
import logging

from app.config import settings
from ...database.core import get_db
from ...models.core import User, RefreshSession, UserProfile, PasswordResetToken
from ...schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse, ForgotPasswordRequest, ResetPasswordRequest, SuccessResponse
from ...services.auth_service import get_password_hash, verify_password, create_access_token, create_refresh_token, verify_token, rate_limiter, generate_reset_token, hash_reset_token
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

REFRESH_COOKIE_NAME = "refresh_token"

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(User).filter(User.email == user_in.email).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
        
    hashed_password = get_password_hash(user_in.password)
    new_user = User(email=user_in.email, hashed_password=hashed_password)
    db.add(new_user)
    db.flush() # flush to get user ID
    
    # Optionally create an initial UserProfile
    profile = UserProfile(user_id=new_user.id, name=user_in.email.split("@")[0])
    db.add(profile)
    
    db.commit()
    db.refresh(new_user)
    return new_user

@router.post("/login", response_model=TokenResponse)
def login(user_in: UserLogin, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == user_in.email).first()
    if not user or not verify_password(user_in.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
        
    # Generate tokens
    access_token = create_access_token(data={"sub": user.id})
    refresh_token, jti, expires_at = create_refresh_token(data={"sub": user.id})
    
    # Store refresh session
    refresh_session = RefreshSession(
        user_id=user.id,
        refresh_token_jti=jti,
        expires_at=expires_at
    )
    db.add(refresh_session)
    db.commit()
    
    # Set HttpOnly Cookie
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=False, # Set to True in production (HTTPS)
        samesite="lax",
        path="/api/auth",
        max_age=7 * 24 * 60 * 60 # 7 days
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    
    if not token:
        raise credentials_exception
        
    try:
        payload = verify_token(token)
        user_id: str = payload.get("sub")
        jti: str = payload.get("jti")
        token_type: str = payload.get("type")
        if user_id is None or jti is None or token_type != "refresh":
            raise credentials_exception
    except Exception:
        raise credentials_exception
        
    # Check DB session
    session = db.query(RefreshSession).filter(RefreshSession.refresh_token_jti == jti).first()
    if not session:
        raise credentials_exception
        
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
        
    if session.revoked or expires_at < datetime.now(timezone.utc):
        raise credentials_exception
        
    # Revoke old session (Rotation)
    session.revoked = True
    db.commit()
    
    # Issue new tokens
    access_token = create_access_token(data={"sub": user_id})
    new_refresh_token, new_jti, new_expires_at = create_refresh_token(data={"sub": user_id})
    
    new_session = RefreshSession(
        user_id=user_id,
        refresh_token_jti=new_jti,
        expires_at=new_expires_at
    )
    db.add(new_session)
    db.commit()
    
    # Set new cookie
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=new_refresh_token,
        httponly=True,
        secure=False, 
        samesite="lax",
        path="/api/auth",
        max_age=7 * 24 * 60 * 60
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    token = request.cookies.get(REFRESH_COOKIE_NAME)
    if token:
        try:
            payload = verify_token(token)
            jti: str = payload.get("jti")
            if jti:
                session = db.query(RefreshSession).filter(RefreshSession.refresh_token_jti == jti).first()
                if session:
                    session.revoked = True
                    db.commit()
        except Exception:
            pass # Ignore token decode errors on logout
            
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/auth")
    return {"ok": True}

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.post("/forgot-password", response_model=SuccessResponse)
def forgot_password(request_data: ForgotPasswordRequest, request: Request, db: Session = Depends(get_db)):
    # Rate Limiting
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"reset_{client_ip}_{request_data.email.lower()}"
    if not rate_limiter.is_allowed(rate_key, limit=3, window_seconds=900): # 3 requests per 15 minutes
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
        
    user = db.query(User).filter(User.email == request_data.email).first()
    
    # Always return success response for anti-enumeration
    success_msg = "If that email exists, a reset link has been sent."
    
    if user:
        # Invalidate any existing unused tokens for this user
        db.query(PasswordResetToken).filter(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used == False
        ).update({"used": True})
        
        raw_token, token_hash = generate_reset_token()
        
        reset_token = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=15)
        )
        db.add(reset_token)
        db.commit()
        
        # In a real system, send email here. 
        # For now, we simulate and optionally log it.
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
        if settings.LOG_RESET_TOKENS_IN_DEV:
            logger.info(f"Password reset link generated for {user.email}: {reset_link}")
            
    return {"message": success_msg}

@router.post("/reset-password", response_model=SuccessResponse)
def reset_password(request_data: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_hash = hash_reset_token(request_data.token)
    
    # Needs to be transactional
    try:
        reset_token = db.query(PasswordResetToken).filter(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used == False,
            PasswordResetToken.expires_at > datetime.now(timezone.utc)
        ).with_for_update().first() # Lock the row for update
        
        if not reset_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token.")
            
        user = db.query(User).filter(User.id == reset_token.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User no longer exists.")
            
        # Update password
        user.hashed_password = get_password_hash(request_data.new_password)
        
        # Mark token as used
        reset_token.used = True
        
        # Revoke all existing refresh sessions to force re-login everywhere
        db.query(RefreshSession).filter(
            RefreshSession.user_id == user.id,
            RefreshSession.revoked == False
        ).update({"revoked": True})
        
        db.commit()
        return {"message": "Password has been successfully reset."}
        
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error during password reset: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred during password reset.")
