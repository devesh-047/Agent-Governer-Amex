"""Hash-chain audit write service (Task 2.2).

所有权: D2

This module implements the hash-chain write function that records
decision events to the audit_log table with cryptographic linkage
to previous records via SHA-256 hashing.

Critical invariants:
1. Canonicalization BEFORE hashing: sort keys alphabetically, strip whitespace
2. Hash formula: SHA256(canonical_json(row) + prev_hash_of_last_row)
3. First row has prev_hash = "" (empty string)
4. Use pg_advisory_xact_lock for global serialization of concurrent writes
5. Amount: float → 2-decimal string → Decimal for storage
6. Timestamp: must be timezone-aware → normalized to UTC → ISO-8601
"""

from __future__ import annotations

import hashlib
import json
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from schemas.audit import AuditWriteResult, DecisionEvent, HashChainError, ChainIntegrityStatus


# PostgreSQL advisory lock key for audit chain serialization
# This key serializes ALL writers to the audit_log table to prevent
# concurrent writes from creating a forked or invalid hash chain.
# Lock is released automatically on transaction commit/rollback.
AUDIT_CHAIN_LOCK_KEY = 123456789


# Dependency injection: allows tests to override with test session factory
_db_session_factory: Callable[[], Session] | None = None

# Python-level lock for additional serialization
# Used in conjunction with pg_advisory_xact_lock for belt-and-suspenders approach
_audit_write_lock = threading.Lock()


def set_db_session_factory(factory: Callable[[], Session]) -> None:
    """Set the database session factory for dependency injection.

    Tests use this to inject a test session factory.
    """
    global _db_session_factory
    _db_session_factory = factory


def reset_db_session_factory() -> None:
    """Reset to default session factory (for tests)."""
    global _db_session_factory
    _db_session_factory = None


def _get_session() -> Session:
    """Get a database session from the configured factory."""
    from db.base import SessionLocal

    factory = _db_session_factory or SessionLocal
    return factory()


def _normalize_amount(amount: float) -> tuple[str, Decimal]:
    """Convert float amount to 2-decimal string and Decimal.

    This ensures the value we hash matches the value stored in PostgreSQL NUMERIC(12,2).

    Returns:
        (amount_str, amount_decimal) - 2-decimal string and Decimal for storage
    """
    amount_str = f"{amount:.2f}"
    amount_decimal = Decimal(amount_str)
    return amount_str, amount_decimal


def _normalize_timestamp(ts: datetime) -> str:
    """Normalize timezone-aware datetime to UTC ISO-8601 string with microseconds.

    Args:
        ts: timezone-aware datetime

    Returns:
        ISO-8601 string like "2026-07-25T14:30:45.123456+00:00"

    Raises:
        ValueError: if ts is naive (no timezone info)
    """
    if ts.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")

    ts_utc = ts.astimezone(timezone.utc)
    # Format: 2026-07-25T14:30:45.123456+00:00
    # strftime %z gives +0000, so we need to insert the colon manually
    ts_str = ts_utc.strftime("%Y-%m-%dT%H:%M:%S.%f%z")
    # Insert colon into timezone offset: +0000 -> +00:00
    if ts_str.endswith("+0000"):
        ts_str = ts_str[:-5] + "+00:00"
    elif ts_str.endswith("-0000"):
        ts_str = ts_str[:-5] + "-00:00"
    else:
        # Handle other timezone offsets (e.g., +0530 -> +05:30)
        if len(ts_str) >= 5 and ts_str[-3] in ("+", "-"):
            ts_str = ts_str[:-2] + ":" + ts_str[-2:]
    return ts_str


def _canonicalize_hash_input(
    action_type: str,
    agent_id: uuid.UUID,
    amount_str: str,
    decision: str,
    policy_version: str,
    reason: str | None,
    reason_code: str,
    timestamp: str,
) -> str:
    """Create canonical JSON representation of the row data for hashing.

    The fields are in alphabetical order as specified in the PRD:
    ["action_type", "agent_id", "amount", "decision", "policy_version",
     "reason", "reason_code", "timestamp"]

    Args:
        action_type: The action being requested
        agent_id: UUID of the agent (will be formatted as hyphenated lowercase string)
        amount_str: 2-decimal amount string (e.g., "25.00")
        decision: "allow" or "deny"
        policy_version: Policy version string
        reason: Human-readable reason or None (becomes JSON null)
        reason_code: Machine-readable reason code
        timestamp: ISO-8601 timestamp string

    Returns:
        Canonical JSON string with sorted keys and no whitespace
    """
    row_data = {
        "action_type": action_type,
        "agent_id": str(agent_id),  # UUID → hyphenated lowercase string
        "amount": amount_str,  # Already 2-decimal string
        "decision": decision,  # lowercase
        "policy_version": policy_version,
        "reason": reason,  # None → JSON null automatically
        "reason_code": reason_code,  # uppercase
        "timestamp": timestamp,  # ISO-8601
    }

    # Sort keys alphabetically, strip whitespace (compact JSON)
    return json.dumps(row_data, separators=(",", ":"), sort_keys=True)


def _compute_hash(canonical_json: str, prev_hash: str) -> str:
    """Compute SHA-256 hash of canonical_json + prev_hash.

    The hash formula is: SHA256(canonical_json(row) + prev_hash)

    Args:
        canonical_json: Canonical JSON representation of the row
        prev_hash: Hash of the previous row (empty string for genesis row)

    Returns:
        64-character hex string
    """
    hash_input = canonical_json + prev_hash
    return hashlib.sha256(hash_input.encode("utf-8")).hexdigest()


def record_decision(event: DecisionEvent) -> AuditWriteResult:
    """Record a decision event to the audit log with hash-chain integrity.

    This function:
    1. Acquires Python-level lock AND PostgreSQL advisory lock to serialize writers
    2. Fetches the last row's hash as prev_hash (empty string if table is empty)
    3. Canonicalizes the event data
    4. Computes the hash
    5. Inserts the new row atomically
    6. Releases both locks (Python lock on exit, PostgreSQL lock on commit)

    Args:
        event: DecisionEvent with all decision details

    Returns:
        AuditWriteResult with the new row's ID and computed hash

    Raises:
        HashChainError: If database operation fails
    """
    # Acquire Python-level lock first (belt-and-suspenders with pg_advisory_xact_lock)
    # This ensures serialization even before we touch the database
    with _audit_write_lock:
        session = _get_session()
        audit_id = uuid.uuid4()

        try:
            # Normalize amount and timestamp for canonicalization
            amount_str, amount_decimal = _normalize_amount(event.amount)
            timestamp_str = _normalize_timestamp(event.timestamp)

            # Create canonical JSON for hashing
            canonical_json = _canonicalize_hash_input(
                action_type=event.action_type,
                agent_id=event.agent_id,
                amount_str=amount_str,
                decision=event.decision,
                policy_version=event.policy_version,
                reason=event.reason,
                reason_code=event.reason_code,
                timestamp=timestamp_str,
            )

            # Get the last row's hash as prev_hash
            # Use pg_advisory_xact_lock for global serialization
            # This lock is released automatically on commit/rollback
            prev_hash = ""
            with session.begin():
                # Acquire advisory lock at transaction scope
                # This serializes ALL writers to the audit_log table
                # The lock is released when the transaction commits or rolls back
                session.execute(text(f"SELECT pg_advisory_xact_lock({AUDIT_CHAIN_LOCK_KEY})"))

                # Fetch the last row's hash (after acquiring lock, so we see committed data)
                # Use FOR UPDATE to lock the row and prevent concurrent modifications
                result = session.execute(
                    text("SELECT hash FROM audit_log ORDER BY timestamp DESC, id DESC LIMIT 1 FOR UPDATE")
                )
                last_row = result.fetchone()
                if last_row is not None:
                    prev_hash = last_row[0]  # First column is the hash
                else:
                    prev_hash = ""  # Genesis row has empty prev_hash

                # Compute the hash for this row
                new_hash = _compute_hash(canonical_json, prev_hash)

                # Insert the new row with explicit timestamp
                # IMPORTANT: We must insert the exact timestamp we hashed,
                # not let PostgreSQL use server_default=func.now()
                session.execute(
                    text("""
                        INSERT INTO audit_log
                        (id, timestamp, agent_id, action_type, amount, decision, reason, reason_code,
                         policy_version, prev_hash, hash)
                        VALUES
                        (:id, :timestamp, :agent_id, :action_type, :amount, :decision, :reason,
                         :reason_code, :policy_version, :prev_hash, :hash)
                    """),
                    {
                        "id": audit_id,
                        "timestamp": event.timestamp,  # Use the exact event timestamp
                        "agent_id": event.agent_id,
                        "action_type": event.action_type,
                        "amount": amount_decimal,  # Store as Decimal
                        "decision": event.decision,
                        "reason": event.reason,
                        "reason_code": event.reason_code,
                        "policy_version": event.policy_version,
                        "prev_hash": prev_hash,
                        "hash": new_hash,
                    },
                )

            return AuditWriteResult(audit_log_id=audit_id, hash=new_hash)

        except Exception as e:
            session.rollback()
            raise HashChainError(f"Failed to record decision: {e}") from e
        finally:
            session.close()
    # Python lock released automatically when we exit the 'with _audit_write_lock' block


def verify_chain() -> ChainIntegrityStatus:
    """Verify the integrity of the entire hash chain.

    Walks the audit log and verifies every stored hash matches what
    record_decision() would have generated.

    This function:
    1. Queries all rows ordered by timestamp, id ASC (same ordering as Task 2.2)
    2. For each row, reconstructs the canonical hash input
    3. Recomputes the hash using the same logic as record_decision()
    4. Compares to stored hash
    5. Returns detailed status of any break detected

    Ordering matches Task 2.2: ORDER BY timestamp ASC, id ASC
    The id tie-breaker ensures deterministic ordering for rows with
    identical timestamps.

    Returns:
        ChainIntegrityStatus with verification results

    Raises:
        HashChainError: If database operation fails
    """
    session = None
    try:
        session = _get_session()
        # Query all rows in chronological order.
        # ORDER BY timestamp ASC, id ASC is the canonical traversal order.
        # The id tie-breaker resolves rows with identical timestamps
        # deterministically — this is the same key ordering used by
        # record_decision() (which selects the previous row with
        # ORDER BY timestamp DESC, id DESC LIMIT 1), so write-order and
        # verification-order stay perfectly aligned.
        result = session.execute(
            text("""
                SELECT id, timestamp, agent_id, action_type, amount, decision,
                       reason, reason_code, policy_version, prev_hash, hash
                FROM audit_log
                ORDER BY timestamp ASC, id ASC
            """)
        )

        rows = result.fetchall()

        # Handle empty chain case
        if not rows:
            return ChainIntegrityStatus(
                intact=True,
                verified_count=0,
                broken_at_row=None,
                first_broken_id=None,
                error_type=None,
                message="Empty audit chain"
            )

        verified_count = 0

        # Verify each row
        for row in rows:
            (
                row_id, row_timestamp, row_agent_id, row_action_type, row_amount,
                row_decision, row_reason, row_reason_code, row_policy_version,
                row_prev_hash, row_hash
            ) = row

            # Normalize fields for canonicalization
            # Convert amount Decimal to 2-decimal string
            amount_str = f"{row_amount:.2f}"

            # Convert timestamp to UTC ISO-8601 string
            timestamp_str = _normalize_timestamp(row_timestamp)

            # Recompute canonical JSON using same logic as record_decision()
            canonical_json = _canonicalize_hash_input(
                action_type=row_action_type,
                agent_id=row_agent_id,
                amount_str=amount_str,
                decision=row_decision,
                policy_version=row_policy_version,
                reason=row_reason,
                reason_code=row_reason_code,
                timestamp=timestamp_str,
            )

            # Recompute hash
            recomputed_hash = _compute_hash(canonical_json, row_prev_hash)

            # Compare to stored hash
            if recomputed_hash != row_hash:
                return ChainIntegrityStatus(
                    intact=False,
                    verified_count=verified_count,
                    broken_at_row=verified_count + 1,
                    first_broken_id=row_id,
                    error_type="HASH_MISMATCH",
                    message=(
                        f"Hash mismatch at row {verified_count + 1}: "
                        f"stored {row_hash} != recomputed {recomputed_hash}"
                    )
                )

            verified_count += 1

        # All rows verified successfully
        return ChainIntegrityStatus(
            intact=True,
            verified_count=verified_count,
            broken_at_row=None,
            first_broken_id=None,
            error_type=None,
            message=f"Chain intact: {verified_count} records verified"
        )

    except Exception as e:
        raise HashChainError(f"Failed to verify chain: {e}") from e
    finally:
        if session is not None:
            session.close()
