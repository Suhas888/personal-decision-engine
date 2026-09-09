"""
tests/pg/conftest.py — PostgreSQL integration test fixtures.

Isolation strategy:
  - Dedicated `pde_test` schema within the same Supabase PostgreSQL instance.
  - Application data lives in `public` — NEVER touched here.
  - Schema created/destroyed per test session via session-scoped fixture.
  - Tables built by alembic upgrade 935deb1afd0f (migration-first, connection injection).
  - Per-test cleanup via TRUNCATE ... CASCADE.

Safety invariants enforced at runtime:
  1. current_schema() MUST equal 'pde_test'
  2. search_path MUST place 'pde_test' first
  3. alembic_version MUST equal '935deb1afd0f'
  4. No get_db or get_current_user override from tests/conftest.py applies here.
"""

import pytest
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database.core import get_db
from app.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TEST_SCHEMA = "pde_test"
MIGRATION_REVISION = "935deb1afd0f"
BACKEND_DIR = Path(__file__).parent.parent.parent  # .../backend/

# FK-safe truncation order (children before parents)
_TRUNCATE_ORDER = [
    "command_confirmations",
    "dynamic_constraints",
    "plan_history",
    "schedule_blocks",
    "plans",
    "preferences",
    "fixed_events",
    "task_dependencies",
    "tasks",
    "user_profiles",
    "refresh_sessions",
    "users",
]

# ---------------------------------------------------------------------------
# Engine factories
# ---------------------------------------------------------------------------

def _make_admin_engine():
    """Engine with default search_path — used only to create/drop pde_test schema."""
    return create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=2,
    )


def _make_test_engine():
    """Engine targeting pde_test schema via connect_args (avoids URL serialization issues)."""
    return create_engine(
        settings.DATABASE_URL,
        connect_args={"options": f"-c search_path={TEST_SCHEMA}"},
        pool_pre_ping=True,
        pool_size=3,
        max_overflow=5,
    )

# ---------------------------------------------------------------------------
# Safety verification
# ---------------------------------------------------------------------------

def _assert_in_test_schema(conn) -> tuple:
    """Fail immediately if the connection is not scoped to pde_test."""
    current = conn.execute(text("SELECT current_schema()")).scalar()
    search_path = conn.execute(text("SHOW search_path")).scalar()
    if current != TEST_SCHEMA:
        raise RuntimeError(
            f"[PG TEST SAFETY VIOLATION] current_schema()={current!r} — "
            f"expected {TEST_SCHEMA!r}. Aborting to protect production data."
        )
    if TEST_SCHEMA not in (search_path or ""):
        raise RuntimeError(
            f"[PG TEST SAFETY VIOLATION] search_path={search_path!r} — "
            f"does not include {TEST_SCHEMA!r}. Aborting."
        )
    return current, search_path


def _record_public_tables(admin_conn) -> list:
    """Snapshot current table names in the public schema."""
    rows = admin_conn.execute(text(
        "SELECT tablename FROM pg_catalog.pg_tables "
        "WHERE schemaname = 'public' ORDER BY tablename"
    )).fetchall()
    return [r[0] for r in rows]

# ---------------------------------------------------------------------------
# Alembic migration via connection injection
# ---------------------------------------------------------------------------

def _run_alembic_via_connection(conn, revision: str, direction: str = "upgrade"):
    """
    Run alembic upgrade/downgrade by injecting a pre-built connection that
    already has search_path=pde_test set. This avoids all URL serialization
    issues with special characters (e.g. %40 in Supabase passwords).
    """
    from alembic.config import Config
    from alembic import command as alembic_cmd

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    # Inject the connection — alembic/env.py checks config.attributes['connection']
    cfg.attributes["connection"] = conn

    if direction == "upgrade":
        alembic_cmd.upgrade(cfg, revision)
    else:
        alembic_cmd.downgrade(cfg, revision)

# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def pg_admin_engine():
    engine = _make_admin_engine()
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def pg_public_tables_snapshot(pg_admin_engine):
    """Record public schema table list before any PG test runs."""
    with pg_admin_engine.connect() as conn:
        return _record_public_tables(conn)


@pytest.fixture(scope="session")
def pg_engine(pg_admin_engine, pg_public_tables_snapshot):
    """
    Session-scoped PostgreSQL test engine:
      1. Create pde_test schema.
      2. Run alembic upgrade 935deb1afd0f → pde_test (via connection injection).
      3. Verify schema identity and migration version.
      4. Yield the engine.
      5. DROP SCHEMA pde_test CASCADE.
      6. Verify public schema is unchanged.
    """
    # 1. Create schema
    with pg_admin_engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
        conn.commit()
    print(f"\n[PG TEST] Schema '{TEST_SCHEMA}' created.")

    # 2. Build test engine (search_path=pde_test via connect_args)
    engine = _make_test_engine()

    # 3. Safety check
    with engine.connect() as conn:
        current, search_path = _assert_in_test_schema(conn)
        print(f"[PG TEST] current_schema()={current!r}  search_path={search_path!r}")

    # 4. Alembic migration via injected connection
    with engine.connect() as conn:
        _run_alembic_via_connection(conn, MIGRATION_REVISION, "upgrade")
    print(f"[PG TEST] alembic upgrade {MIGRATION_REVISION} -> {TEST_SCHEMA} complete.")

    # 5. Verify
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        assert version == MIGRATION_REVISION, (
            f"Expected alembic_version={MIGRATION_REVISION!r}, got {version!r}"
        )
        tables = conn.execute(text(
            "SELECT tablename FROM pg_catalog.pg_tables "
            f"WHERE schemaname = '{TEST_SCHEMA}' ORDER BY tablename"
        )).fetchall()
        table_names = [t[0] for t in tables]
        print(f"[PG TEST] pde_test tables ({len(table_names)}): {table_names}")
        assert len(table_names) >= 13  # 12 app tables + alembic_version

    yield engine

    # Teardown: drop schema
    print(f"\n[PG TEST] Dropping schema '{TEST_SCHEMA}' CASCADE …")
    with pg_admin_engine.connect() as conn:
        conn.execute(text(f"DROP SCHEMA IF EXISTS {TEST_SCHEMA} CASCADE"))
        conn.commit()
    print(f"[PG TEST] Schema '{TEST_SCHEMA}' dropped.")

    # Verify public schema unchanged
    with pg_admin_engine.connect() as conn:
        current_public = _record_public_tables(conn)
    original = pg_public_tables_snapshot
    assert sorted(current_public) == sorted(original), (
        f"[PG TEST SAFETY] public schema changed!\n"
        f"  Before: {original}\n  After:  {current_public}"
    )
    print("[PG TEST] public schema protection: OK — tables unchanged.")

    engine.dispose()


@pytest.fixture(scope="session")
def pg_SessionFactory(pg_engine):
    return sessionmaker(bind=pg_engine, autocommit=False, autoflush=True)

# ---------------------------------------------------------------------------
# Per-test session + cleanup
# ---------------------------------------------------------------------------

@pytest.fixture()
def pg_session(pg_engine, pg_SessionFactory):
    """
    Function-scoped session wired to pde_test.
    After each test, TRUNCATE all application tables CASCADE for clean state.
    """
    session = pg_SessionFactory()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    # Clear any overrides from the parent conftest, install our own
    app.dependency_overrides.clear()
    app.dependency_overrides[get_db] = override_get_db

    yield session

    app.dependency_overrides.pop(get_db, None)
    try:
        session.rollback()
    except Exception:
        pass
    session.close()

    # Clean all data for next test
    truncate_sql = ", ".join(_TRUNCATE_ORDER)
    with pg_engine.connect() as conn:
        conn.execute(text(f"TRUNCATE TABLE {truncate_sql} CASCADE"))
        conn.commit()


@pytest.fixture()
def pg_client(pg_session):
    """
    FastAPI TestClient backed by real PostgreSQL (pde_test).
    get_db → pg_session.  get_current_user → NOT overridden (real JWT).
    """
    return TestClient(app, raise_server_exceptions=True)

# ---------------------------------------------------------------------------
# Pre-registered test users
# ---------------------------------------------------------------------------

def _register_and_login(client: TestClient, email: str, password: str) -> dict:
    reg = client.post("/api/auth/register", json={"email": email, "password": password})
    assert reg.status_code == 201, f"Register failed ({email}): {reg.text}"
    user_id = reg.json()["id"]

    login = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, f"Login failed ({email}): {login.text}"
    token = login.json()["access_token"]

    return {
        "id": user_id,
        "email": email,
        "password": password,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture()
def pg_user_a(pg_client):
    return _register_and_login(pg_client, "user_a@pde-pgtest.com", "SecurePass_A1!")


@pytest.fixture()
def pg_user_b(pg_client):
    return _register_and_login(pg_client, "user_b@pde-pgtest.com", "SecurePass_B2!")
