import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.database.core import Base, get_db
from app.models.core import User, RefreshSession
from app.api.dependencies import get_current_user

from sqlalchemy.pool import StaticPool

client = TestClient(app)

@pytest.fixture(scope="function", autouse=True)
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    app.dependency_overrides[get_db] = lambda: session
    
    app.dependency_overrides.pop(get_current_user, None)
    
    yield session
    
    app.dependency_overrides.clear()
    session.close()

def test_register_success():
    response = client.post("/api/auth/register", json={"email": "test@example.com", "password": "password123"})
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert "id" in response.json()
    assert "hashed_password" not in response.json()

def test_register_duplicate():
    client.post("/api/auth/register", json={"email": "dup@example.com", "password": "password123"})
    response = client.post("/api/auth/register", json={"email": "dup@example.com", "password": "newpassword"})
    assert response.status_code == 400

def test_login_success():
    client.post("/api/auth/register", json={"email": "login@example.com", "password": "password123"})
    response = client.post("/api/auth/login", json={"email": "login@example.com", "password": "password123"})
    assert response.status_code == 200
    assert "access_token" in response.json()
    # Check that refresh_token cookie is set
    assert "refresh_token" in response.cookies

def test_login_invalid():
    client.post("/api/auth/register", json={"email": "login2@example.com", "password": "password123"})
    response = client.post("/api/auth/login", json={"email": "login2@example.com", "password": "wrong"})
    assert response.status_code == 401

def test_refresh_token_rotation():
    client.post("/api/auth/register", json={"email": "refresh@example.com", "password": "password123"})
    login_resp = client.post("/api/auth/login", json={"email": "refresh@example.com", "password": "password123"})
    refresh_cookie = client.cookies.get("refresh_token")
    assert refresh_cookie is not None
    
    refresh_resp = client.post("/api/auth/refresh")
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    new_refresh_cookie = client.cookies.get("refresh_token")
    assert new_refresh_cookie != refresh_cookie
    
    # Try using old refresh token again (should fail)
    client.cookies.set("refresh_token", refresh_cookie)
    fail_refresh = client.post("/api/auth/refresh")
    assert fail_refresh.status_code == 401
    
def test_logout():
    client.post("/api/auth/register", json={"email": "logout@example.com", "password": "password123"})
    client.post("/api/auth/login", json={"email": "logout@example.com", "password": "password123"})
    client.post("/api/auth/logout")
    
    # Refresh should fail now
    fail_refresh = client.post("/api/auth/refresh")
    assert fail_refresh.status_code == 401

def test_me_protected():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    
    client.post("/api/auth/register", json={"email": "me@example.com", "password": "password123"})
    login_resp = client.post("/api/auth/login", json={"email": "me@example.com", "password": "password123"})
    access_token = login_resp.json()["access_token"]
    
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "me@example.com"
