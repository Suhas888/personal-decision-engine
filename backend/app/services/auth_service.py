import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
import jwt
import bcrypt

# Patch passlib + bcrypt compatibility bug (passlib 1.7.4 passes >72 byte strings to bcrypt in detect_wrap_bug)
_orig_hashpw = bcrypt.hashpw
def _safe_hashpw(password, salt):
    if isinstance(password, bytes) and len(password) > 72:
        password = password[:72]
    return _orig_hashpw(password, salt)
bcrypt.hashpw = _safe_hashpw

from passlib.context import CryptContext

from app.config import settings

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    safe_password = plain_password[:72] if plain_password else ""
    return pwd_context.verify(safe_password, hashed_password)


def get_password_hash(password: str) -> str:
    safe_password = password[:72] if password else ""
    return pwd_context.hash(safe_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict) -> Tuple[str, str, datetime]:
    import uuid
    to_encode = data.copy()
    jti = str(uuid.uuid4())
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "jti": jti, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, jti, expire


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token")


import secrets
import hashlib
from collections import defaultdict

class RateLimiter:
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        raise NotImplementedError

class InMemoryRateLimiter(RateLimiter):
    def __init__(self):
        self._store = defaultdict(list)
    
    def is_allowed(self, key: str, limit: int, window_seconds: int) -> bool:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=window_seconds)
        self._store[key] = [t for t in self._store[key] if t > cutoff]
        
        if len(self._store[key]) >= limit:
            return False
        
        self._store[key].append(now)
        return True

# Singleton instance
rate_limiter = InMemoryRateLimiter()

def generate_reset_token() -> Tuple[str, str]:
    """Generates a secure random token and its SHA-256 hash."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    return raw_token, token_hash

def hash_reset_token(token: str) -> str:
    """Hashes a raw token using SHA-256."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
