"""
conftest.py — shared pytest fixtures.

Legacy tests (test_crud, test_phase6, test_replan, test_e2e_stage7b, …) run
against an in-memory SQLite database so they are fully isolated from the real
PostgreSQL instance and can use the mock 'default_user' without FK violations.

test_pg_integration.py intentionally bypasses these overrides and uses the
real PostgreSQL connection configured in .env.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.api.dependencies import get_current_user
from app.database.core import Base, get_db
from app.models.core import User


# ---------------------------------------------------------------------------
# Mock user (no FK: SQLite in-memory tables have no 'users' row required)
# ---------------------------------------------------------------------------

class MockUser:
    id = "default_user"
    user_id = "default_user"
    email = "test@example.com"
    hashed_password = "fake"


def override_get_current_user():
    return MockUser()


# ---------------------------------------------------------------------------
# Shared in-memory SQLite engine (module-level singleton)
# ---------------------------------------------------------------------------

_SQLITE_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
_SqliteSession = sessionmaker(bind=_SQLITE_ENGINE)


def _sqlite_get_db():
    """FastAPI dependency: yields a SQLite session."""
    db = _SqliteSession()
    try:
        yield db
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Session-scoped setup: create all SQLite tables once per test run
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def create_sqlite_tables():
    """Create all ORM tables in the shared SQLite engine before any tests run."""
    Base.metadata.create_all(bind=_SQLITE_ENGINE)
    yield
    Base.metadata.drop_all(bind=_SQLITE_ENGINE)


# ---------------------------------------------------------------------------
# Fixtures that expose the SQLite engine/session factory to individual tests
# ---------------------------------------------------------------------------

@pytest.fixture()
def _sqlite_engine():
    """Yield the shared in-memory SQLite engine."""
    return _SQLITE_ENGINE


@pytest.fixture()
def _sqlite_session_factory():
    """Return a sessionmaker bound to the shared SQLite engine."""
    return _SqliteSession


# ---------------------------------------------------------------------------
# Function-scoped autouse: redirect DB + auth for every non-PG test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_auth_override(request):
    """
    For all tests EXCEPT test_pg_integration and tests/pg/* directory, override:
      - get_db           → in-memory SQLite session
      - get_current_user → MockUser()

    PostgreSQL tests manage their own database wiring via tests/pg/conftest.py.
    """
    fspath = str(request.fspath).replace("\\", "/")
    is_pg_test = (
        "test_pg_integration" in request.fspath.basename
        or "/tests/pg/" in fspath
        or fspath.endswith("/pg/conftest.py")
    )
    if is_pg_test:
        yield
        return

    app.dependency_overrides[get_db] = _sqlite_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_current_user, None)
