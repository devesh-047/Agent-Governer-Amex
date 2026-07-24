"""create audit log table

Revision ID: 6a7a2b38c0bc
Revises: 09ee32e4e00a
Create Date: 2026-07-24 16:51:05.913142

Append-only audit log with hash-chain integrity for tamper detection.
All decisions (allow and deny) are recorded.

所有权: D2
依赖: agents table (09ee32e4e00a)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '6a7a2b38c0bc'
down_revision: Union[str, Sequence[str], None] = '09ee32e4e00a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema - create audit_log table with append-only protection."""

    decision_enum = postgresql.ENUM(
        'allow',
        'deny',
        name='decision_enum',
        create_type=False,
    )
    reason_code_enum = postgresql.ENUM(
        'IDENTITY_FAILED',
        'FLEET_HALTED',
        'AGENT_REVOKED',
        'PERMISSION_DENIED',
        'AMOUNT_EXCEEDS_LIMIT',
        'SPEND_CAP_EXCEEDED',
        'RUNTIME_STATE_UNAVAILABLE',
        'OK',
        name='reason_code_enum',
        create_type=False,
    )

    op.execute("CREATE TYPE decision_enum AS ENUM ('allow', 'deny')")
    op.execute(
        """
        CREATE TYPE reason_code_enum AS ENUM (
            'IDENTITY_FAILED',
            'FLEET_HALTED',
            'AGENT_REVOKED',
            'PERMISSION_DENIED',
            'AMOUNT_EXCEEDS_LIMIT',
            'SPEND_CAP_EXCEEDED',
            'RUNTIME_STATE_UNAVAILABLE',
            'OK'
        )
        """
    )

    # Create audit_log table
    op.create_table(
        'audit_log',
        sa.Column(
            'id',
            sa.UUID(),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            'timestamp',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'agent_id',
            sa.UUID(),
            sa.ForeignKey('agents.id', ondelete='RESTRICT'),
            nullable=False,
        ),
        sa.Column(
            'action_type',
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            'amount',
            sa.Numeric(precision=12, scale=2),
            nullable=False,
        ),
        sa.Column(
            'decision',
            decision_enum,
            nullable=False,
        ),
        sa.Column(
            'reason',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'reason_code',
            reason_code_enum,
            nullable=False,
        ),
        sa.Column(
            'policy_version',
            sa.String(100),
            nullable=False,
        ),
        sa.Column(
            'prev_hash',
            sa.String(64),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column(
            'hash',
            sa.String(64),
            nullable=False,
        ),
    )

    op.execute("REVOKE UPDATE, DELETE, TRUNCATE ON TABLE audit_log FROM PUBLIC")

    # Create indexes for query performance
    op.create_index('ix_audit_log_timestamp', 'audit_log', ['timestamp'])
    op.create_index('ix_audit_log_agent_id', 'audit_log', ['agent_id'])
    op.create_index('ix_audit_log_action_type', 'audit_log', ['action_type'])
    op.create_index('ix_audit_log_decision', 'audit_log', ['decision'])

    # Create append-only trigger (blocks UPDATE, DELETE, and TRUNCATE)
    op.execute("""
        CREATE FUNCTION block_audit_log_mutations() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'Append-only: audit_log table does not allow % operations', TG_OP;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Drop any existing old trigger (from previous migration runs)
    op.execute('DROP TRIGGER IF EXISTS audit_log_append_only_trigger ON audit_log')

    op.execute("""
        CREATE TRIGGER audit_log_append_only_row_trigger
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION block_audit_log_mutations();
    """)

    op.execute("""
        CREATE TRIGGER audit_log_append_only_truncate_trigger
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION block_audit_log_mutations();
    """)


def downgrade() -> None:
    """Downgrade schema - drop audit_log table and ENUMs."""

    # Drop indexes first (they don't depend on triggers)
    op.drop_index('ix_audit_log_decision', 'audit_log')
    op.drop_index('ix_audit_log_action_type', 'audit_log')
    op.drop_index('ix_audit_log_agent_id', 'audit_log')
    op.drop_index('ix_audit_log_timestamp', 'audit_log')

    # Drop triggers (handle both old and new names for safety)
    op.execute('DROP TRIGGER IF EXISTS audit_log_append_only_truncate_trigger ON audit_log')
    op.execute('DROP TRIGGER IF EXISTS audit_log_append_only_row_trigger ON audit_log')
    op.execute('DROP TRIGGER IF EXISTS audit_log_append_only_trigger ON audit_log')

    # Drop table
    op.drop_table('audit_log')

    # Drop function (triggers are gone)
    op.execute('DROP FUNCTION IF EXISTS block_audit_log_mutations()')

    # Drop ENUM types
    op.execute('DROP TYPE IF EXISTS decision_enum')
    op.execute('DROP TYPE IF EXISTS reason_code_enum')
