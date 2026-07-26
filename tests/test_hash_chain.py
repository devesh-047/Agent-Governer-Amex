"""Comprehensive tests for Task 2.2: hash-chain write function.

Tests cover:
- Genesis record (prev_hash="")
- Second record linking to first
- Deterministic hashing
- Amount canonicalization (float → Decimal string)
- Timestamp canonicalization (timezone-aware, UTC)
- Nullable reason (None → JSON null)
- Concurrent writes with pg_advisory_xact_lock (empty and non-empty tables)
- Stored hash recomputation after DB round-trip
- Multiple agents in global chain
"""

from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from db.base import SessionLocal, engine
from db.models.agent import Agent
from db.models.audit_log import AuditLog
from schemas.audit import DecisionEvent, AuditWriteResult, HashChainError
from services.hash_chain import (
    record_decision,
    set_db_session_factory,
    reset_db_session_factory,
    AUDIT_CHAIN_LOCK_KEY,
    _normalize_amount,
    _normalize_timestamp,
    _canonicalize_hash_input,
    _compute_hash,
)


@pytest.fixture(autouse=True)
def cleanup_audit_log():
    """Automatically clean up audit_log after each test."""
    yield
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        try:
            conn.execute(text("TRUNCATE TABLE audit_log CASCADE"))
        finally:
            conn.execute(text("SET session_replication_role = DEFAULT"))


@pytest.fixture
def test_agent():
    """Create a test agent for audit entries."""
    agent_id = uuid.uuid4()
    agent = Agent(
        id=agent_id,
        name="Hash Chain Test Agent",
        permissions=["refund"],
        max_single_amount=Decimal("50.00"),
        daily_cap=Decimal("100.00"),
        status="active",
        shared_secret="test-secret",
    )
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO agents (id, name, permissions, max_single_amount, daily_cap, status, shared_secret)
                VALUES (:id, :name, CAST(:permissions AS jsonb), :max_single_amount, :daily_cap, :status, :shared_secret)
            """),
            {
                "id": agent_id,
                "name": agent.name,
                "permissions": '["refund"]',
                "max_single_amount": agent.max_single_amount,
                "daily_cap": agent.daily_cap,
                "status": agent.status,
                "shared_secret": agent.shared_secret,
            }
        )
    return agent


def test_normalize_amount_two_decimals():
    """Test amount normalization preserves 2-decimal precision."""
    amount_str, amount_decimal = _normalize_amount(25.0)
    assert amount_str == "25.00"
    assert amount_decimal == Decimal("25.00")


def test_normalize_amount_rounds_to_two_decimals():
    """Test amount normalization rounds to 2 decimals."""
    amount_str, amount_decimal = _normalize_amount(25.456)
    assert amount_str == "25.46"
    assert amount_decimal == Decimal("25.46")


def test_normalize_amount_negative():
    """Test negative amount normalization."""
    amount_str, amount_decimal = _normalize_amount(-10.5)
    assert amount_str == "-10.50"
    assert amount_decimal == Decimal("-10.50")


def test_normalize_timestamp_utc():
    """Test timestamp normalization to UTC ISO-8601."""
    ts = datetime(2026, 7, 25, 14, 30, 45, 123456, tzinfo=timezone.utc)
    result = _normalize_timestamp(ts)
    assert result == "2026-07-25T14:30:45.123456+00:00"


def test_normalize_timestamp_converts_to_utc():
    """Test timestamp normalization converts non-UTC to UTC."""
    # Eastern Time (UTC-5 in summer, UTC-4 in winter - using EST as example)
    from datetime import timezone, timedelta
    est = timezone(timedelta(hours=-5))
    ts = datetime(2026, 7, 25, 9, 30, 45, 123456, tzinfo=est)
    result = _normalize_timestamp(ts)
    assert result == "2026-07-25T14:30:45.123456+00:00"


def test_normalize_timestamp_raises_on_naive():
    """Test naive datetime raises ValueError."""
    ts = datetime(2026, 7, 25, 14, 30, 45, 123456)  # No tzinfo
    with pytest.raises(ValueError, match="timezone-aware"):
        _normalize_timestamp(ts)


def test_canonicalize_hash_input_sorted_keys():
    """Test canonicalization sorts keys alphabetically."""
    result = _canonicalize_hash_input(
        action_type="refund",
        agent_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        amount_str="25.00",
        decision="allow",
        policy_version="1.0",
        reason="Test reason",
        reason_code="OK",
        timestamp="2026-07-25T14:30:45.123456+00:00",
    )
    # Verify keys are sorted by parsing the JSON
    import json
    data = json.loads(result)
    keys = list(data.keys())
    assert keys == ["action_type", "agent_id", "amount", "decision", "policy_version", "reason", "reason_code", "timestamp"]


def test_canonicalize_hash_input_compact_json():
    """Test canonicalization produces compact JSON (no whitespace)."""
    result = _canonicalize_hash_input(
        action_type="refund",
        agent_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        amount_str="25.00",
        decision="allow",
        policy_version="1.0",
        reason="Test reason",
        reason_code="OK",
        timestamp="2026-07-25T14:30:45.123456+00:00",
    )
    # Compact JSON has no spaces after colons or commas
    assert ": " not in result
    assert ", " not in result


def test_canonicalize_hash_input_nullable_reason():
    """Test None reason becomes JSON null."""
    result = _canonicalize_hash_input(
        action_type="refund",
        agent_id=uuid.UUID("123e4567-e89b-12d3-a456-426614174000"),
        amount_str="25.00",
        decision="deny",
        policy_version="1.0",
        reason=None,
        reason_code="SPEND_CAP_EXCEEDED",
        timestamp="2026-07-25T14:30:45.123456+00:00",
    )
    import json
    data = json.loads(result)
    assert data["reason"] is None


def test_compute_hash_deterministic():
    """Test hash computation is deterministic."""
    canonical = '{"action_type":"refund","agent_id":"123e4567-e89b-12d3-a456-426614174000","amount":"25.00","decision":"allow","policy_version":"1.0","reason":"Test","reason_code":"OK","timestamp":"2026-07-25T14:30:45.123456+00:00"}'
    prev_hash = "abc123"
    result = _compute_hash(canonical, prev_hash)
    assert len(result) == 64
    # Verify it's a valid hex string
    assert all(c in "0123456789abcdef" for c in result)
    # Verify determinism - same input produces same output
    result2 = _compute_hash(canonical, prev_hash)
    assert result == result2
    # Verify it matches the known correct value for this input
    assert result == "edabf9f87e56f3d04314137b1f8f4cc145cca6b7eec86a5761ff394a3ec05423"


def test_compute_hash_genesis():
    """Test genesis hash (empty prev_hash)."""
    canonical = '{"action_type":"refund","agent_id":"123e4567-e89b-12d3-a456-426614174000","amount":"25.00","decision":"allow","policy_version":"1.0","reason":"Test","reason_code":"OK","timestamp":"2026-07-25T14:30:45.123456+00:00"}'
    result = _compute_hash(canonical, "")
    assert len(result) == 64
    # Verify it's a valid hex string
    assert all(c in "0123456789abcdef" for c in result)
    # Empty prev_hash means just hash of canonical
    assert result == "6592c21ad3bde7f3827af4e32b2ba8cc82a5b2a6a5683cdf3d2b2f020947afd4"


def test_record_decision_genesis_row(test_agent):
    """Test first record has empty prev_hash."""
    event = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=25.0,
        decision="allow",
        policy_version="1.0",
        reason="Test reason",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )

    result = record_decision(event)

    assert isinstance(result, AuditWriteResult)
    assert result.audit_log_id is not None
    assert len(result.hash) == 64

    # Verify stored in DB
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT prev_hash, hash FROM audit_log WHERE id = :id"),
            {"id": result.audit_log_id}
        ).fetchone()
        assert row is not None
        assert row[0] == ""  # prev_hash is empty for genesis
        assert row[1] == result.hash


def test_record_decision_second_row_links_to_first(test_agent):
    """Test second record has prev_hash pointing to first."""
    event1 = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=25.0,
        decision="allow",
        policy_version="1.0",
        reason="First",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )
    result1 = record_decision(event1)

    event2 = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=10.0,
        decision="allow",
        policy_version="1.0",
        reason="Second",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    result2 = record_decision(event2)

    # Verify second row's prev_hash equals first row's hash
    with SessionLocal() as session:
        row2 = session.execute(
            text("SELECT prev_hash, hash FROM audit_log WHERE id = :id"),
            {"id": result2.audit_log_id}
        ).fetchone()
        assert row2 is not None
        assert row2[0] == result1.hash
        assert row2[1] == result2.hash


def test_record_decision_deny_with_null_reason(test_agent):
    """Test deny decision with null reason stores correctly."""
    event = DecisionEvent(
        action_type="transfer",
        agent_id=test_agent.id,
        amount=999.0,
        decision="deny",
        policy_version="1.0",
        reason=None,  # Null reason
        reason_code="AMOUNT_EXCEEDS_LIMIT",
        timestamp=datetime.now(timezone.utc),
    )

    result = record_decision(event)

    # Verify reason is NULL in DB
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT reason FROM audit_log WHERE id = :id"),
            {"id": result.audit_log_id}
        ).fetchone()
        assert row is not None
        assert row[0] is None


def test_record_decision_amount_precision(test_agent):
    """Test amount is stored with 2-decimal precision."""
    event = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=25.456,  # More than 2 decimals
        decision="allow",
        policy_version="1.0",
        reason="Test",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )

    result = record_decision(event)

    # Verify amount is rounded to 2 decimals
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT amount FROM audit_log WHERE id = :id"),
            {"id": result.audit_log_id}
        ).fetchone()
        assert row is not None
        assert row[0] == Decimal("25.46")


def test_hash_recomputation_after_db_roundtrip(test_agent):
    """Test hash computed before INSERT matches hash recomputed from stored row."""
    ts = datetime(2026, 7, 25, 14, 30, 45, 123456, tzinfo=timezone.utc)
    event = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=25.5,
        decision="allow",
        policy_version="1.0",
        reason="Test reason",
        reason_code="OK",
        timestamp=ts,
    )

    result = record_decision(event)

    # Fetch the stored row
    with SessionLocal() as session:
        row = session.execute(
            text("""
                SELECT agent_id, action_type, amount, decision, reason,
                       reason_code, policy_version, timestamp, prev_hash, hash
                FROM audit_log WHERE id = :id
            """),
            {"id": result.audit_log_id}
        ).fetchone()

        assert row is not None

        # Recompute canonical input from stored values
        agent_id_stored, action_type_stored, amount_stored, decision_stored, reason_stored, reason_code_stored, policy_version_stored, timestamp_stored, prev_hash_stored, hash_stored = row

        # Convert amount to 2-decimal string
        amount_str = f"{amount_stored:.2f}"

        # Convert timestamp to ISO-8601 using the same normalization function
        ts_str = _normalize_timestamp(timestamp_stored)

        # Recompute canonical JSON
        canonical_recomputed = _canonicalize_hash_input(
            action_type=action_type_stored,
            agent_id=agent_id_stored,
            amount_str=amount_str,
            decision=decision_stored,
            policy_version=policy_version_stored,
            reason=reason_stored,
            reason_code=reason_code_stored,
            timestamp=ts_str,
        )

        # Recompute hash
        hash_recomputed = _compute_hash(canonical_recomputed, prev_hash_stored)

        # Should match stored hash
        assert hash_recomputed == hash_stored
        assert hash_recomputed == result.hash


def test_multiple_agents_in_global_chain(test_agent):
    """Test multiple agents write to the same global hash chain."""
    agent2_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO agents (id, name, permissions, max_single_amount, daily_cap, status, shared_secret)
                VALUES (:id, :name, CAST(:permissions AS jsonb), :max_single_amount, :daily_cap, :status, :shared_secret)
            """),
            {
                "id": agent2_id,
                "name": "Second Agent",
                "permissions": '["transfer"]',
                "max_single_amount": Decimal("100.00"),
                "daily_cap": Decimal("200.00"),
                "status": "active",
                "shared_secret": "secret2",
            }
        )

    event1 = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=10.0,
        decision="allow",
        policy_version="1.0",
        reason="Agent 1",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )
    result1 = record_decision(event1)

    event2 = DecisionEvent(
        action_type="transfer",
        agent_id=agent2_id,
        amount=50.0,
        decision="allow",
        policy_version="1.0",
        reason="Agent 2",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc) + timedelta(seconds=1),
    )
    result2 = record_decision(event2)

    # Verify agent 2's prev_hash points to agent 1's hash (global chain)
    with SessionLocal() as session:
        row2 = session.execute(
            text("SELECT prev_hash FROM audit_log WHERE id = :id"),
            {"id": result2.audit_log_id}
        ).fetchone()
        assert row2 is not None
        assert row2[0] == result1.hash


def test_concurrent_writes_empty_table(test_agent):
    """Test concurrent writes to empty table produce only one genesis record."""
    results = []
    errors = []

    def write_record(record_id: int):
        try:
            event = DecisionEvent(
                action_type="refund",
                agent_id=test_agent.id,
                amount=float(record_id),
                decision="allow",
                policy_version="1.0",
                reason=f"Record {record_id}",
                reason_code="OK",
                timestamp=datetime.now(timezone.utc) + timedelta(microseconds=record_id),
            )
            result = record_decision(event)
            results.append((record_id, result))
        except Exception as e:
            errors.append((record_id, e))

    # Launch 5 concurrent writes
    threads = []
    for i in range(5):
        t = threading.Thread(target=write_record, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # All writes should succeed
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 5

    # Verify only ONE record has empty prev_hash (genesis)
    with SessionLocal() as session:
        genesis_count = session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE prev_hash = ''")
        ).scalar()
        assert genesis_count == 1

        # Verify the chain is intact
        # Use verify_chain() rather than raw SQL ordering check.
        # The hash chain write order (determined by advisory lock) may differ
        # from timestamp order when threads have pre-assigned future timestamps.
        # verify_chain() correctly validates each row's hash regardless of
        # timestamp ordering — this is the actual correctness invariant.
        from services.hash_chain import verify_chain
        chain_result = verify_chain()
        assert chain_result.intact is True, f"Chain broken: {chain_result.message}"


def test_concurrent_writes_nonempty_table(test_agent):
    """Test concurrent writes to non-empty table don't fork the chain."""
    # First, create a genesis record
    genesis_event = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=100.0,
        decision="allow",
        policy_version="1.0",
        reason="Genesis",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )
    genesis_result = record_decision(genesis_event)

    results = []
    errors = []

    def write_record(record_id: int):
        try:
            event = DecisionEvent(
                action_type="refund",
                agent_id=test_agent.id,
                amount=float(record_id),
                decision="allow",
                policy_version="1.0",
                reason=f"Record {record_id}",
                reason_code="OK",
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=record_id),
            )
            result = record_decision(event)
            results.append((record_id, result))
        except Exception as e:
            errors.append((record_id, e))

    # Launch 10 concurrent writes
    threads = []
    for i in range(10):
        t = threading.Thread(target=write_record, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    # All writes should succeed
    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == 10

    # Verify only ONE record has empty prev_hash (the original genesis)
    with SessionLocal() as session:
        genesis_count = session.execute(
            text("SELECT COUNT(*) FROM audit_log WHERE prev_hash = ''")
        ).scalar()
        assert genesis_count == 1

        # Verify the chain is intact (no forks)
        # Use verify_chain() for the same reason as the empty-table test:
        # write order (advisory lock) vs timestamp order can differ.
        from services.hash_chain import verify_chain
        chain_result = verify_chain()
        assert chain_result.intact is True, f"Chain broken: {chain_result.message}"

        # Verify we have 11 rows total (1 genesis + 10 concurrent)
        total_count = session.execute(
            text("SELECT COUNT(*) FROM audit_log")
        ).scalar()
        assert total_count == 11


def test_stress_concurrent_writes(test_agent):
    """Stress test with many concurrent writers."""
    num_writes = 50
    results = []
    errors = []

    def write_record(record_id: int):
        try:
            event = DecisionEvent(
                action_type="refund",
                agent_id=test_agent.id,
                amount=float(record_id * 0.1),
                decision="allow",
                policy_version="1.0",
                reason=f"Stress {record_id}",
                reason_code="OK",
                timestamp=datetime.now(timezone.utc) + timedelta(milliseconds=record_id),
            )
            result = record_decision(event)
            results.append((record_id, result))
        except Exception as e:
            errors.append((record_id, e))

    threads = []
    for i in range(num_writes):
        t = threading.Thread(target=write_record, args=(i,))
        threads.append(t)

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    assert len(errors) == 0, f"Errors occurred: {errors}"
    assert len(results) == num_writes

    # Use verify_chain() for hash-chain correctness.
    # The stress test uses pre-assigned future timestamps that threads pick
    # up in arrival order, which may differ from timestamp ascending order.
    # verify_chain() validates each row's hash against its stored prev_hash,
    # which is the actual integrity guarantee — not "rows link in ts order".
    from services.hash_chain import verify_chain
    chain_result = verify_chain()
    assert chain_result.intact is True, f"Chain broken: {chain_result.message}"


def test_set_db_session_factory():
    """Test dependency injection for session factory."""
    # This test verifies the function exists and is callable
    # Actual testing of injected sessions is complex and typically
    # covered by integration tests

    # Should not raise
    from db.base import SessionLocal
    set_db_session_factory(SessionLocal)

    # Reset to default
    reset_db_session_factory()


def test_hash_chain_error_on_invalid_agent():
    """Test HashChainError raised for invalid agent_id."""
    invalid_agent_id = uuid.uuid4()  # Not in DB

    event = DecisionEvent(
        action_type="refund",
        agent_id=invalid_agent_id,
        amount=25.0,
        decision="allow",
        policy_version="1.0",
        reason="Test",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )

    with pytest.raises(HashChainError):
        record_decision(event)


# ============================================================================
# verify_chain() Tests (Task 2.3)
# ============================================================================

from services.hash_chain import verify_chain
from schemas.audit import ChainIntegrityStatus


def test_verify_chain_valid_intact(test_agent):
    """All hashes match - chain intact."""
    # Create 3 rows with record_decision()
    events = [
        DecisionEvent(
            action_type="refund",
            agent_id=test_agent.id,
            amount=float(i),
            decision="allow",
            policy_version="1.0",
            reason=f"Record {i}",
            reason_code="OK",
            timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
        )
        for i in range(3)
    ]

    for event in events:
        record_decision(event)

    # Verify chain
    result = verify_chain()

    assert result.intact is True
    assert result.verified_count == 3
    assert result.broken_at_row is None
    assert result.first_broken_id is None
    assert result.error_type is None
    assert "intact" in result.message.lower()


def test_verify_chain_broken_hash_middle(test_agent):
    """Row N has wrong hash - detected by verify_chain."""
    # Create 3 rows
    events = [
        DecisionEvent(
            action_type="refund",
            agent_id=test_agent.id,
            amount=float(i),
            decision="allow",
            policy_version="1.0",
            reason=f"Record {i}",
            reason_code="OK",
            timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
        )
        for i in range(3)
    ]

    for event in events:
        record_decision(event)

    # Modify row 2 hash directly via SQL (simulate tampering)
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        try:
            # PostgreSQL UPDATE with ctid for single row
            conn.execute(
                text("UPDATE audit_log SET hash = '0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef' "
                      "WHERE ctid = (SELECT ctid FROM audit_log ORDER BY timestamp LIMIT 1 OFFSET 1)")
            )
        finally:
            conn.execute(text("SET session_replication_role = DEFAULT"))

    # Verify chain detects break
    result = verify_chain()

    assert result.intact is False
    assert result.verified_count == 1  # First row verified, second broke
    assert result.broken_at_row == 2
    assert result.error_type == "HASH_MISMATCH"
    assert "mismatch" in result.message.lower()


def test_verify_chain_modified_row(test_agent):
    """Row data changed, hash mismatch detected."""
    # Create a row
    event = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=25.0,
        decision="allow",
        policy_version="1.0",
        reason="Original",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )
    record_decision(event)

    # Modify amount via SQL (simulate tampering)
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        try:
            conn.execute(text("UPDATE audit_log SET amount = 999.99"))
        finally:
            conn.execute(text("SET session_replication_role = DEFAULT"))

    # Verify chain detects mismatch
    result = verify_chain()

    assert result.intact is False
    assert result.broken_at_row == 1
    assert result.error_type == "HASH_MISMATCH"


def test_verify_chain_empty():
    """No rows exist - chain is intact with 0 records."""
    # Ensure clean state
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        try:
            conn.execute(text("TRUNCATE TABLE audit_log CASCADE"))
        finally:
            conn.execute(text("SET session_replication_role = DEFAULT"))

    result = verify_chain()

    assert result.intact is True
    assert result.verified_count == 0
    assert "empty" in result.message.lower()


def test_verify_chain_single_row(test_agent):
    """Only genesis row exists."""
    event = DecisionEvent(
        action_type="refund",
        agent_id=test_agent.id,
        amount=10.0,
        decision="allow",
        policy_version="1.0",
        reason="Genesis",
        reason_code="OK",
        timestamp=datetime.now(timezone.utc),
    )
    record_decision(event)

    result = verify_chain()

    assert result.intact is True
    assert result.verified_count == 1


def test_verify_chain_db_failure():
    """Postgres unavailable during verification raises HashChainError."""
    # This test uses dependency injection to simulate DB failure
    from db.base import SessionLocal

    # Save original factory
    from services.hash_chain import _db_session_factory, set_db_session_factory

    original_factory = _db_session_factory

    # Mock failing session factory
    def failing_session_factory():
        raise Exception("Database connection failed")

    set_db_session_factory(failing_session_factory)

    try:
        with pytest.raises(HashChainError, match="Failed to verify chain"):
            verify_chain()
    finally:
        # Restore original factory
        if original_factory:
            set_db_session_factory(original_factory)
        else:
            set_db_session_factory(SessionLocal)


def test_verify_chain_security_database_operations(test_agent):
    """Verify chain detects any change using supported database operations."""
    # Create a valid chain
    events = [
        DecisionEvent(
            action_type="refund",
            agent_id=test_agent.id,
            amount=float(i),
            decision="allow",
            policy_version="1.0",
            reason=f"Record {i}",
            reason_code="OK",
            timestamp=datetime.now(timezone.utc) + timedelta(seconds=i),
        )
        for i in range(5)
    ]

    for event in events:
        record_decision(event)

    # Verify chain is intact before tampering
    result_before = verify_chain()
    assert result_before.intact is True
    assert result_before.verified_count == 5

    # Tamper with a row using UPDATE (supported database operation)
    with engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        try:
            # Change decision from allow to deny using ctid
            conn.execute(
                text("UPDATE audit_log SET decision = 'deny' "
                      "WHERE ctid = (SELECT ctid FROM audit_log WHERE decision = 'allow' LIMIT 1)")
            )
        finally:
            conn.execute(text("SET session_replication_role = DEFAULT"))

    # Verify chain detects the tampering
    result_after = verify_chain()
    assert result_after.intact is False
    assert result_after.error_type == "HASH_MISMATCH"
    assert result_after.broken_at_row >= 1

    # Verify the break is at the modified row
    with SessionLocal() as session:
        # Find the modified row
        modified_row = session.execute(
            text("SELECT id, timestamp FROM audit_log WHERE decision = 'deny'")
        ).fetchone()

        assert modified_row is not None
        assert result_after.first_broken_id == modified_row[0]


def test_verify_chain_ordering_with_duplicate_timestamps(test_agent):
    """Chain handles rows with identical timestamps using id tie-breaker."""
    # Create rows with identical timestamps (microseconds will differ slightly)
    base_time = datetime(2026, 7, 25, 12, 0, 0, 0, tzinfo=timezone.utc)

    events = [
        DecisionEvent(
            action_type="refund",
            agent_id=test_agent.id,
            amount=float(i),
            decision="allow",
            policy_version="1.0",
            reason=f"Record {i}",
            reason_code="OK",
            timestamp=base_time,  # Same timestamp
        )
        for i in range(3)
    ]

    for event in events:
        record_decision(event)

    # Verify chain handles deterministic ordering
    result = verify_chain()

    assert result.intact is True
    assert result.verified_count == 3

    # Verify ordering by timestamp, id
    with SessionLocal() as session:
        rows = session.execute(
            text("SELECT id FROM audit_log ORDER BY timestamp ASC, id ASC")
        ).fetchall()

        assert len(rows) == 3
        # All rows should be verified in this order
        assert result.verified_count == len(rows)
