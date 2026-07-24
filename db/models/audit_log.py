# db/models/audit_log.py

"""
Audit Log Model (Task 2.1).

Append-only audit log with hash-chain integrity.
All decisions (allow and deny) are recorded for tamper detection.

所有权: D2
依赖: Agent model (db/models/agent.py) - FK to agents.id
"""

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.sql import func

from db.base import Base


DECISION_ENUM = ENUM("allow", "deny", name="decision_enum", create_type=False)
REASON_CODE_ENUM = ENUM(
    "IDENTITY_FAILED",
    "FLEET_HALTED",
    "AGENT_REVOKED",
    "PERMISSION_DENIED",
    "AMOUNT_EXCEEDS_LIMIT",
    "SPEND_CAP_EXCEEDED",
    "RUNTIME_STATE_UNAVAILABLE",
    "OK",
    name="reason_code_enum",
    create_type=False,
)


class AuditLog(Base):
    """Audit log table for recording all decisions with hash-chain integrity."""
    __tablename__ = "audit_log"

    __table_args__ = (
        Index("ix_audit_log_timestamp", "timestamp"),
        Index("ix_audit_log_agent_id", "agent_id"),
        Index("ix_audit_log_action_type", "action_type"),
        Index("ix_audit_log_decision", "decision"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    timestamp = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
    )

    action_type = Column(String(100), nullable=False)

    amount = Column(Numeric(12, 2), nullable=False)

    decision = Column(DECISION_ENUM, nullable=False)

    reason = Column(Text, nullable=True)

    reason_code = Column(REASON_CODE_ENUM, nullable=False)

    policy_version = Column(String(100), nullable=False)

    prev_hash = Column(String(64), nullable=False, default="", server_default=text("''"))

    hash = Column(String(64), nullable=False)
