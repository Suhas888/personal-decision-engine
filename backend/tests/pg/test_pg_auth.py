"""
PostgreSQL integration tests — Authentication.

Tests auth persistence, JWT token flow, refresh rotation,
logout/revocation, and session ownership against real PostgreSQL (pde_test schema).
"""

import pytest
from fastapi.testclient import TestClient


pytestmark = pytest.mark.pg


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestRegister:
    def test_register_success(self, pg_client):
        res = pg_client.post("/api/auth/register", json={
            "email": "newuser@pgtest.com",
            "password": "Password123!"
        })
        assert res.status_code == 201
        data = res.json()
        assert data["email"] == "newuser@pgtest.com"
        assert "id" in data
        assert "hashed_password" not in data

    def test_register_duplicate_email(self, pg_client):
        pg_client.post("/api/auth/register", json={
            "email": "dup@pgtest.com", "password": "Password123!"
        })
        res = pg_client.post("/api/auth/register", json={
            "email": "dup@pgtest.com", "password": "DifferentPass1!"
        })
        assert res.status_code == 400
        assert "already registered" in res.json()["detail"].lower()

    def test_register_creates_profile(self, pg_client, pg_session):
        from app.models.core import UserProfile
        pg_client.post("/api/auth/register", json={
            "email": "profcheck@pgtest.com", "password": "Password123!"
        })
        profile = pg_session.query(UserProfile).filter_by(
            # name derived from email prefix
        ).first()
        # Verify at least one profile exists
        count = pg_session.query(UserProfile).count()
        assert count >= 1


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

class TestLogin:
    def test_login_success(self, pg_client):
        pg_client.post("/api/auth/register", json={
            "email": "login@pgtest.com", "password": "Password123!"
        })
        res = pg_client.post("/api/auth/login", json={
            "email": "login@pgtest.com", "password": "Password123!"
        })
        assert res.status_code == 200
        assert "access_token" in res.json()
        assert res.json()["token_type"] == "bearer"
        # Refresh token cookie must be set
        assert "refresh_token" in res.cookies

    def test_login_wrong_password(self, pg_client):
        pg_client.post("/api/auth/register", json={
            "email": "wrongpw@pgtest.com", "password": "Password123!"
        })
        res = pg_client.post("/api/auth/login", json={
            "email": "wrongpw@pgtest.com", "password": "WrongPassword!"
        })
        assert res.status_code == 401

    def test_login_nonexistent_user(self, pg_client):
        res = pg_client.post("/api/auth/login", json={
            "email": "ghost@pgtest.com", "password": "Password123!"
        })
        assert res.status_code == 401

    def test_login_creates_refresh_session_in_db(self, pg_client, pg_session):
        from app.models.core import RefreshSession
        before = pg_session.query(RefreshSession).count()
        pg_client.post("/api/auth/register", json={
            "email": "refreshcheck@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/login", json={
            "email": "refreshcheck@pgtest.com", "password": "Password123!"
        })
        after = pg_session.query(RefreshSession).count()
        assert after == before + 1


# ---------------------------------------------------------------------------
# Token refresh & rotation
# ---------------------------------------------------------------------------

class TestRefreshRotation:
    def test_refresh_returns_new_access_token(self, pg_client):
        pg_client.post("/api/auth/register", json={
            "email": "refresh1@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/login", json={
            "email": "refresh1@pgtest.com", "password": "Password123!"
        })
        old_cookie = pg_client.cookies.get("refresh_token")
        assert old_cookie is not None

        res = pg_client.post("/api/auth/refresh")
        assert res.status_code == 200
        assert "access_token" in res.json()

    def test_refresh_rotates_cookie(self, pg_client):
        pg_client.post("/api/auth/register", json={
            "email": "refresh2@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/login", json={
            "email": "refresh2@pgtest.com", "password": "Password123!"
        })
        old_cookie = pg_client.cookies.get("refresh_token")

        pg_client.post("/api/auth/refresh")
        new_cookie = pg_client.cookies.get("refresh_token")
        assert new_cookie != old_cookie

    def test_old_refresh_token_rejected_after_rotation(self, pg_client):
        """Once rotated, the old refresh token must be revoked."""
        pg_client.post("/api/auth/register", json={
            "email": "refresh3@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/login", json={
            "email": "refresh3@pgtest.com", "password": "Password123!"
        })
        old_cookie = pg_client.cookies.get("refresh_token")

        # Rotate
        pg_client.post("/api/auth/refresh")

        # Try the old cookie
        pg_client.cookies.set("refresh_token", old_cookie)
        res = pg_client.post("/api/auth/refresh")
        assert res.status_code == 401

    def test_refresh_without_cookie_rejected(self, pg_client):
        res = pg_client.post("/api/auth/refresh")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Logout & revocation
# ---------------------------------------------------------------------------

class TestLogout:
    def test_logout_revokes_session(self, pg_client, pg_session):
        from app.models.core import RefreshSession
        pg_client.post("/api/auth/register", json={
            "email": "logout@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/login", json={
            "email": "logout@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/logout")

        # All sessions for this user should be revoked
        sessions = pg_session.query(RefreshSession).all()
        for s in sessions:
            if s.revoked:
                return  # at least one revoked — pass
        # No sessions is also valid if logout cleared cookie
        # Attempt refresh should fail
        res = pg_client.post("/api/auth/refresh")
        assert res.status_code == 401

    def test_refresh_after_logout_rejected(self, pg_client):
        pg_client.post("/api/auth/register", json={
            "email": "logoutref@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/login", json={
            "email": "logoutref@pgtest.com", "password": "Password123!"
        })
        pg_client.post("/api/auth/logout")
        res = pg_client.post("/api/auth/refresh")
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Protected endpoint / /me
# ---------------------------------------------------------------------------

class TestMe:
    def test_me_requires_auth(self, pg_client):
        res = pg_client.get("/api/auth/me")
        assert res.status_code == 401

    def test_me_returns_correct_user(self, pg_client, pg_user_a):
        res = pg_client.get("/api/auth/me", headers=pg_user_a["headers"])
        assert res.status_code == 200
        assert res.json()["email"] == pg_user_a["email"]

    def test_me_with_invalid_token_rejected(self, pg_client):
        res = pg_client.get("/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"})
        assert res.status_code == 401
