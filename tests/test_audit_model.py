"""Focused tests for Task 2.1: audit_log model and migration.

These tests verify the shipped PostgreSQL schema, append-only protections,
and the Alembic revision chain without touching later audit/hash-chain logic.
"""

from __future__ import annotations

import importlib.util
import uuid
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from db.base import SessionLocal, engine
from db.models.agent import Agent
from db.models.audit_log import AuditLog


ALEMBIC_INI = ROOT / "alembic.ini"
MIGRATION_PATH = ROOT / "alembic" / "versions" / "6a7a2b38c0bc_create_audit_log_table.py"

EXPECTED_DECISION_VALUES = {"allow", "deny"}
EXPECTED_REASON_CODE_VALUES = {
    "IDENTITY_FAILED",
    "FLEET_HALTED",
    "AGENT_REVOKED",
    "PERMISSION_DENIED",
    "AMOUNT_EXCEEDS_LIMIT",
    "SPEND_CAP_EXCEEDED",
    "RUNTIME_STATE_UNAVAILABLE",
    "OK",
}


def _alembic_config(connection):
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    config.attributes["connection"] = connection
    return config


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("audit_migration", MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _force_cleanup(agent_id: uuid.UUID, audit_id: uuid.UUID | None = None) -> None:
    """Force cleanup of test data by bypassing triggers. Must run in a separate transaction."""
    # Use engine.begin() for proper transaction handling and automatic commit/rollback
    with engine.begin() as connection:
        try:
            # Bypass triggers for cleanup
            connection.execute(text("SET session_replication_role = replica"))
            try:
                if audit_id is not None:
                    connection.execute(text("DELETE FROM audit_log WHERE id = :audit_id"), {"audit_id": audit_id})
                connection.execute(text("DELETE FROM audit_log WHERE agent_id = :agent_id"), {"agent_id": agent_id})
                connection.execute(text("DELETE FROM agents WHERE id = :agent_id"), {"agent_id": agent_id})
            finally:
                # Always restore replication role
                connection.execute(text("SET session_replication_role = DEFAULT"))
        except Exception:
            # If anything fails, rollback the transaction (handled by engine.begin())
            raise


def _create_test_agent() -> tuple[Agent, uuid.UUID]:
    """Create a test agent and return (agent, agent_id). Caller is responsible for cleanup."""
    import json
    agent_id = uuid.uuid4()
    agent = Agent(
        id=agent_id,
        name="Audit Test Agent",
        permissions=["refund"],
        max_single_amount=Decimal("50.00"),
        daily_cap=Decimal("100.00"),
        status="active",
        shared_secret="audit-test-secret",
    )
    with engine.begin() as connection:
        # Use JSON string with cast operator in the parameter
        connection.execute(
            text("""
                INSERT INTO agents (id, name, permissions, max_single_amount, daily_cap, status, shared_secret)
                VALUES (:id, :name, CAST(:permissions AS jsonb), :max_single_amount, :daily_cap, :status, :shared_secret)
            """),
            {
                "id": agent_id,
                "name": agent.name,
                "permissions": json.dumps(agent.permissions),
                "max_single_amount": agent.max_single_amount,
                "daily_cap": agent.daily_cap,
                "status": agent.status,
                "shared_secret": agent.shared_secret,
            }
        )
    return agent, agent_id


def _seed_audit_row(agent_id: uuid.UUID, **overrides) -> uuid.UUID:
    """Seed an audit log row and return its ID. Caller is responsible for cleanup."""
    audit_id = uuid.uuid4()
    action_type = overrides.get("action_type", "refund")
    amount = overrides.get("amount", Decimal("25.00"))
    decision = overrides.get("decision", "allow")
    reason = overrides.get("reason")
    reason_code = overrides.get("reason_code", "OK")
    policy_version = overrides.get("policy_version", "1.0")
    prev_hash = overrides.get("prev_hash", "")
    hash_val = overrides.get("hash", "a" * 64)

    with engine.begin() as connection:
        connection.execute(
            text("""
                INSERT INTO audit_log (id, agent_id, action_type, amount, decision, reason, reason_code, policy_version, prev_hash, hash)
                VALUES (:id, :agent_id, :action_type, :amount, :decision, :reason, :reason_code, :policy_version, :prev_hash, :hash)
            """),
            {
                "id": audit_id,
                "agent_id": agent_id,
                "action_type": action_type,
                "amount": amount,
                "decision": decision,
                "reason": reason,
                "reason_code": reason_code,
                "policy_version": policy_version,
                "prev_hash": prev_hash,
                "hash": hash_val,
            }
        )
    return audit_id


def test_migration_revision_metadata():
    module = _load_migration_module()
    assert module.revision == "6a7a2b38c0bc"
    assert module.down_revision == "09ee32e4e00a"


def test_schema_matches_contract():
    inspector = inspect(engine)

    assert "audit_log" in inspector.get_table_names()

    columns = {column["name"]: column for column in inspector.get_columns("audit_log")}
    assert set(columns) == {
        "id",
        "timestamp",
        "agent_id",
        "action_type",
        "amount",
        "decision",
        "reason",
        "reason_code",
        "policy_version",
        "prev_hash",
        "hash",
    }

    assert columns["id"]["nullable"] is False
    assert columns["timestamp"]["nullable"] is False
    assert columns["timestamp"]["default"] is not None
    assert columns["agent_id"]["nullable"] is False
    assert columns["action_type"]["nullable"] is False
    assert columns["amount"]["nullable"] is False
    assert columns["reason"]["nullable"] is True
    assert columns["reason_code"]["nullable"] is False
    assert columns["policy_version"]["nullable"] is False
    assert columns["prev_hash"]["nullable"] is False
    assert columns["hash"]["nullable"] is False

    assert "UUID" in str(columns["id"]["type"]).upper()
    assert "UUID" in str(columns["agent_id"]["type"]).upper()
    assert "NUMERIC" in str(columns["amount"]["type"]).upper()

    indexes = {index["name"] for index in inspector.get_indexes("audit_log")}
    assert {
        "ix_audit_log_timestamp",
        "ix_audit_log_agent_id",
        "ix_audit_log_action_type",
        "ix_audit_log_decision",
    }.issubset(indexes)

    foreign_keys = inspector.get_foreign_keys("audit_log")
    fk = next((item for item in foreign_keys if item["constrained_columns"] == ["agent_id"]), None)
    assert fk is not None
    assert fk["referred_table"] == "agents"
    assert fk["referred_columns"] == ["id"]

    with engine.connect() as connection:
        decision_values = {
            row[0]
            for row in connection.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'decision_enum'::regtype ORDER BY enumsortorder")
            )
        }
        reason_code_values = {
            row[0]
            for row in connection.execute(
                text("SELECT enumlabel FROM pg_enum WHERE enumtypid = 'reason_code_enum'::regtype ORDER BY enumsortorder")
            )
        }

    assert decision_values == EXPECTED_DECISION_VALUES
    assert reason_code_values == EXPECTED_REASON_CODE_VALUES


def test_insert_round_trip_and_defaults():
    agent, agent_id = _create_test_agent()
    try:
        audit_id = _seed_audit_row(agent_id, reason="Threshold check passed", reason_code="OK", prev_hash="")

        with engine.connect() as connection:
            result = connection.execute(text("SELECT * FROM audit_log WHERE id = :id"), {"id": audit_id})
            row = result.fetchone()
            assert row is not None
            assert str(row[0]) == str(audit_id)  # id
            assert row[3] == "refund"  # action_type
            assert row[4] == Decimal("25.00")  # amount
            assert row[5] == "allow"  # decision
            assert row[6] == "Threshold check passed"  # reason
            assert row[7] == "OK"  # reason_code
            assert row[8] == "1.0"  # policy_version
            assert row[9] == ""  # prev_hash
            assert len(row[10]) == 64  # hash
            assert row[1] is not None  # timestamp

        _force_cleanup(agent_id, audit_id)
    except Exception:
        _force_cleanup(agent_id)
        raise


@pytest.mark.parametrize(
    "sql, params",
    [
        (
            "UPDATE audit_log SET reason = :reason WHERE id = :audit_id",
            {"reason": "mutated"},
        ),
        (
            "DELETE FROM audit_log WHERE id = :audit_id",
            {},
        ),
        (
            "TRUNCATE audit_log",
            {},
        ),
    ],
)
def test_append_only_protection_blocks_mutations(sql, params):
    agent, agent_id = _create_test_agent()
    try:
        audit_id = _seed_audit_row(agent_id, reason_code="OK", prev_hash="")
        params = dict(params)
        # Add audit_id if the SQL references it
        if ":audit_id" in sql:
            params["audit_id"] = audit_id

        with pytest.raises(DBAPIError, match="Append-only"):
            with engine.begin() as connection:
                connection.execute(text(sql), params)

        _force_cleanup(agent_id, audit_id)
    except Exception:
        _force_cleanup(agent_id)
        raise


def test_fk_constraint_blocks_invalid_agent():
    invalid_agent_id = uuid.uuid4()
    audit_id = uuid.uuid4()

    try:
        with engine.begin() as connection:
            with pytest.raises(IntegrityError):
                connection.execute(
                    text("""
                        INSERT INTO audit_log (id, agent_id, action_type, amount, decision, reason_code, policy_version, prev_hash, hash)
                        VALUES (:id, :agent_id, :action_type, :amount, :decision, :reason_code, :policy_version, :prev_hash, :hash)
                    """),
                    {
                        "id": audit_id,
                        "agent_id": invalid_agent_id,
                        "action_type": "refund",
                        "amount": Decimal("10.00"),
                        "decision": "allow",
                        "reason_code": "OK",
                        "policy_version": "1.0",
                        "prev_hash": "",
                        "hash": "b" * 64,
                    }
                )
    finally:
        # No cleanup needed - the insert should have failed
        pass


def test_migration_upgrade_and_downgrade_cycle():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            config = _alembic_config(connection)

            command.downgrade(config, "09ee32e4e00a")
            inspector = inspect(connection)
            assert "audit_log" not in inspector.get_table_names()

            command.upgrade(config, "head")
            inspector = inspect(connection)
            assert "audit_log" in inspector.get_table_names()

            columns = {column["name"] for column in inspector.get_columns("audit_log")}
            assert "reason_code" in columns
            assert "prev_hash" in columns
        finally:
            transaction.rollback()
