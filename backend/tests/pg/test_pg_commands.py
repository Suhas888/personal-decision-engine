"""
PostgreSQL integration tests — Command preview/execute lifecycle.

Tests command confirmation CRUD, expiry, consumption idempotency,
and ownership enforcement against real PostgreSQL (pde_test schema).
LLM calls are mocked to isolate DB behavior.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.schemas.commands import Command, Operation, TargetType, Scope

pytestmark = pytest.mark.pg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fake_parse_delete_all(text: str):
    return [Command(operation=Operation.DELETE, target_type=TargetType.TASK, scope=Scope.ALL)]


def _create_tasks_for_user(pg_session, user_id: str, count: int = 2):
    from app.models.core import Task
    tasks = [
        Task(user_id=user_id, title=f"PG-Task-{i}", estimated_minutes=30)
        for i in range(count)
    ]
    pg_session.add_all(tasks)
    pg_session.commit()
    return tasks


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

class TestCommandPreview:
    def test_preview_returns_confirmation_id(self, pg_client, pg_session, pg_user_a):
        _create_tasks_for_user(pg_session, pg_user_a["id"])

        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            res = pg_client.post("/api/commands/preview", json={"message": "delete all tasks"}, headers=pg_user_a["headers"])

        assert res.status_code == 200
        data = res.json()
        assert data["requires_confirmation"] is True
        assert data["confirmation_id"] is not None
        assert data["affected_count"] == 2

    def test_preview_stores_confirmation_in_db(self, pg_client, pg_session, pg_user_a):
        from app.models.core import CommandConfirmation
        _create_tasks_for_user(pg_session, pg_user_a["id"])

        before = pg_session.query(CommandConfirmation).count()
        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            pg_client.post("/api/commands/preview", json={"message": "delete all tasks"}, headers=pg_user_a["headers"])

        pg_session.expire_all()
        after = pg_session.query(CommandConfirmation).count()
        assert after == before + 1


# ---------------------------------------------------------------------------
# Execute
# ---------------------------------------------------------------------------

class TestCommandExecute:
    def test_execute_deletes_tasks(self, pg_client, pg_session, pg_user_a):
        from app.models.core import Task
        _create_tasks_for_user(pg_session, pg_user_a["id"], count=3)

        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            preview_res = pg_client.post("/api/commands/preview",
                                         json={"message": "delete all tasks"}, headers=pg_user_a["headers"])
            conf_id = preview_res.json()["confirmation_id"]

            exec_res = pg_client.post("/api/commands/execute",
                                      json={"confirmation_id": conf_id}, headers=pg_user_a["headers"])

        assert exec_res.status_code == 200
        pg_session.expire_all()
        remaining = pg_session.query(Task).filter_by(user_id=pg_user_a["id"]).count()
        assert remaining == 0

    def test_confirmation_consumed_after_execute(self, pg_client, pg_session, pg_user_a):
        from app.models.core import CommandConfirmation
        _create_tasks_for_user(pg_session, pg_user_a["id"])

        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            preview_res = pg_client.post("/api/commands/preview",
                                         json={"message": "delete all tasks"}, headers=pg_user_a["headers"])
            conf_id = preview_res.json()["confirmation_id"]
            pg_client.post("/api/commands/execute", json={"confirmation_id": conf_id}, headers=pg_user_a["headers"])

        pg_session.expire_all()
        conf = pg_session.query(CommandConfirmation).filter_by(id=conf_id).first()
        assert conf is not None
        assert conf.consumed is True

    def test_replay_rejected_after_consume(self, pg_client, pg_session, pg_user_a):
        """Re-executing an already-consumed confirmation must return 409."""
        _create_tasks_for_user(pg_session, pg_user_a["id"])

        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            preview_res = pg_client.post("/api/commands/preview",
                                         json={"message": "delete all tasks"}, headers=pg_user_a["headers"])
            conf_id = preview_res.json()["confirmation_id"]
            pg_client.post("/api/commands/execute", json={"confirmation_id": conf_id}, headers=pg_user_a["headers"])

            # Replay
            replay_res = pg_client.post("/api/commands/execute",
                                        json={"confirmation_id": conf_id}, headers=pg_user_a["headers"])

        assert replay_res.status_code == 409


# ---------------------------------------------------------------------------
# Expiry
# ---------------------------------------------------------------------------

class TestCommandExpiry:
    def test_expired_confirmation_rejected(self, pg_client, pg_session, pg_user_a):
        from app.models.core import CommandConfirmation
        _create_tasks_for_user(pg_session, pg_user_a["id"])

        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            preview_res = pg_client.post("/api/commands/preview",
                                         json={"message": "delete all tasks"}, headers=pg_user_a["headers"])
            conf_id = preview_res.json()["confirmation_id"]

        # Manually expire
        pg_session.expire_all()
        conf = pg_session.query(CommandConfirmation).filter_by(id=conf_id).first()
        conf.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        pg_session.commit()

        exec_res = pg_client.post("/api/commands/execute",
                                  json={"confirmation_id": conf_id}, headers=pg_user_a["headers"])

        assert exec_res.status_code == 409


# ---------------------------------------------------------------------------
# Ownership
# ---------------------------------------------------------------------------

class TestCommandOwnership:
    def test_user_b_cannot_execute_user_a_confirmation(self, pg_client, pg_session,
                                                        pg_user_a, pg_user_b):
        from app.models.core import Task
        _create_tasks_for_user(pg_session, pg_user_a["id"])

        with patch("app.api.routes.commands.parse_commands_from_text", side_effect=_fake_parse_delete_all):
            preview_res = pg_client.post("/api/commands/preview",
                                         json={"message": "delete all tasks"}, headers=pg_user_a["headers"])
            conf_id = preview_res.json()["confirmation_id"]

        # User B tries to execute
        exec_res = pg_client.post("/api/commands/execute",
                                  json={"confirmation_id": conf_id}, headers=pg_user_b["headers"])

        assert exec_res.status_code in (404, 403, 409)

        # User A's tasks must still be there
        pg_session.expire_all()
        remaining = pg_session.query(Task).filter_by(user_id=pg_user_a["id"]).count()
        assert remaining == 2
