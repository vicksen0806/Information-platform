"""remove offline feature tables

Revision ID: 20260412_rm_offline_tables
Revises:
Create Date: 2026-04-12 15:40:00
"""

from alembic import op
import sqlalchemy as sa


revision = "20260412_rm_offline_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("crawl_results_source_id_fkey", "crawl_results", type_="foreignkey")
    op.drop_column("crawl_results", "source_id")

    op.drop_table("notification_routes")
    op.drop_table("push_subscriptions")
    op.drop_table("sources")
    op.drop_table("user_email_configs")
    op.drop_table("user_schedule_configs")


def downgrade() -> None:
    op.create_table(
        "user_schedule_configs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("schedule_hour", sa.Integer(), nullable=False),
        sa.Column("schedule_minute", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "user_email_configs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("smtp_host", sa.String(length=255), nullable=False),
        sa.Column("smtp_port", sa.Integer(), nullable=False),
        sa.Column("smtp_user", sa.String(length=255), nullable=False),
        sa.Column("smtp_password_enc", sa.Text(), nullable=False),
        sa.Column("smtp_from", sa.String(length=255), nullable=False),
        sa.Column("smtp_to", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id"),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("search_query", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("crawl_interval_hours", sa.Integer(), nullable=False),
        sa.Column("last_crawled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_sources_user_id"), "sources", ["user_id"], unique=False)

    op.create_table(
        "push_subscriptions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("endpoint"),
    )
    op.create_index(op.f("ix_push_subscriptions_user_id"), "push_subscriptions", ["user_id"], unique=False)

    op.create_table(
        "notification_routes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("group_name", sa.String(length=100), nullable=True),
        sa.Column("webhook_type", sa.String(length=20), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_notification_routes_user_id"), "notification_routes", ["user_id"], unique=False)

    op.add_column("crawl_results", sa.Column("source_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "crawl_results_source_id_fkey",
        "crawl_results",
        "sources",
        ["source_id"],
        ["id"],
        ondelete="CASCADE",
    )
