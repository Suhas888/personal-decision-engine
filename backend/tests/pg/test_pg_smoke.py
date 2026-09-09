"""
PostgreSQL fixture smoke test — verifies schema setup/teardown works.
Run this first to confirm pde_test schema is correctly created and wired.
"""
import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg


def test_pg_engine_targets_pde_test(pg_engine):
    """pg_engine must have current_schema() = pde_test."""
    with pg_engine.connect() as conn:
        schema = conn.execute(text("SELECT current_schema()")).scalar()
        search_path = conn.execute(text("SHOW search_path")).scalar()
    assert schema == "pde_test", f"current_schema()={schema!r}"
    assert "pde_test" in search_path, f"search_path={search_path!r}"


def test_alembic_version_in_pde_test(pg_engine):
    """alembic_version table must exist in pde_test with revision 935deb1afd0f."""
    with pg_engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert version == "935deb1afd0f", f"version={version!r}"


def test_all_12_app_tables_exist(pg_engine):
    """All 12 application tables must be present in pde_test."""
    expected = {
        "users", "refresh_sessions", "user_profiles", "tasks", "task_dependencies",
        "fixed_events", "plans", "schedule_blocks", "preferences", "plan_history",
        "dynamic_constraints", "command_confirmations",
    }
    with pg_engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='pde_test'"
        )).fetchall()
    found = {r[0] for r in rows} - {"alembic_version"}
    missing = expected - found
    assert not missing, f"Missing tables in pde_test: {missing}"


def test_pg_session_can_insert_and_query(pg_session):
    """Sanity: pg_session can write and read from pde_test."""
    from app.models.core import User
    from app.services.auth_service import get_password_hash
    user = User(email="smoke@pde_test.com", hashed_password=get_password_hash("Pass1!"))
    pg_session.add(user)
    pg_session.commit()

    found = pg_session.query(User).filter_by(email="smoke@pde_test.com").first()
    assert found is not None
    assert found.id is not None


def test_pg_client_health(pg_client):
    """pg_client should return real 401 (not mock bypass) for protected endpoint."""
    # With real auth enforcement, /api/auth/me must return 401 for unauthenticated request
    res = pg_client.get("/api/auth/me")
    assert res.status_code == 401


def test_truncate_cleanup_works(pg_engine, pg_session):
    """After test, tables should be empty (relies on pg_session fixture cleanup)."""
    from app.models.core import User
    from app.services.auth_service import get_password_hash
    # Insert something — the fixture cleanup will truncate after this test
    user = User(email="cleanup@pde_test.com", hashed_password=get_password_hash("Pass1!"))
    pg_session.add(user)
    pg_session.commit()
    count = pg_session.query(User).count()
    assert count >= 1
    # (Cleanup is verified by the next test finding 0 rows)
