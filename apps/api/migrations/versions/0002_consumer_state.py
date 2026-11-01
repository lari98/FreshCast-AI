"""Consumer state: idempotency ledger and committed partition versions.

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create consumer-side tables."""
    op.create_table(
        "processed_events",
        sa.Column("event_id", sa.Uuid, primary_key=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "partition_state",
        sa.Column("partition_key", sa.String(130), primary_key=True),
        sa.Column("committed_version", sa.Integer, nullable=False),
    )


def downgrade() -> None:
    """Drop consumer-side tables."""
    op.drop_table("partition_state")
    op.drop_table("processed_events")
