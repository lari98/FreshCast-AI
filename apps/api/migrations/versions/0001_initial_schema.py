"""Initial schema: stock lots, versions, outbox, proposals, audit log.

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all tables."""
    op.create_table(
        "stock_lots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("store_id", sa.String(64), nullable=False, index=True),
        sa.Column("sku", sa.String(64), nullable=False, index=True),
        sa.Column("lot_id", sa.String(64), nullable=False),
        sa.Column("quantity", sa.Integer, nullable=False),
        sa.Column("use_by_date", sa.Date, nullable=False),
        sa.UniqueConstraint("store_id", "lot_id"),
        sa.CheckConstraint("quantity >= 0", name="ck_stock_lots_quantity_nonneg"),
    )
    op.create_table(
        "entity_versions",
        sa.Column("partition_key", sa.String(130), primary_key=True),
        sa.Column("version", sa.Integer, nullable=False),
    )
    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.Uuid, primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("partition_key", sa.String(130), nullable=False, index=True),
        sa.Column("entity_version", sa.Integer, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "order_proposals",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("store_id", sa.String(64), nullable=False, index=True),
        sa.Column("sku", sa.String(64), nullable=False, index=True),
        sa.Column("inputs", sa.JSON, nullable=False),
        sa.Column("usable_stock_units", sa.Integer, nullable=False),
        sa.Column("expiring_stock_units", sa.Integer, nullable=False),
        sa.Column("target_stock_units", sa.Integer, nullable=False),
        sa.Column("recommended_order_units", sa.Integer, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_by", sa.String(128), nullable=False),
        sa.Column("approved_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("entity", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
    )


def downgrade() -> None:
    """Drop all tables."""
    for table in (
        "audit_log",
        "order_proposals",
        "outbox_events",
        "entity_versions",
        "stock_lots",
    ):
        op.drop_table(table)
