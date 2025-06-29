"""Add provider system tables

Revision ID: 003_add_provider_system
Revises: 002_chat_system
Create Date: 2024-06-24 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "003_add_provider_system"
down_revision = "002_chat_system"
branch_labels = None
depends_on = None


def upgrade():
    # Create providers table
    op.create_table(
        "providers",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("config", sa.Text(), nullable=False),  # JSON as TEXT
        sa.Column("is_enabled", sa.Boolean(), nullable=True, default=True),
        sa.Column("is_healthy", sa.Boolean(), nullable=True, default=True),
        sa.Column("priority", sa.Integer(), nullable=True, default=1),
        sa.Column("capabilities", sa.Text(), nullable=True),  # JSON as TEXT
        sa.Column("rate_limits", sa.Text(), nullable=True),  # JSON as TEXT
        sa.Column("last_health_check", sa.DateTime(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=True, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_providers_id"), "providers", ["id"], unique=False)
    op.create_index(op.f("ix_providers_type"), "providers", ["type"], unique=False)

    # Create provider_metrics table
    op.create_table(
        "provider_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider_id", sa.String(), nullable=False),
        sa.Column("metric_type", sa.String(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("metadata", sa.Text(), nullable=True),  # JSON as TEXT
        sa.ForeignKeyConstraint(
            ["provider_id"],
            ["providers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_provider_metrics_id"), "provider_metrics", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_provider_metrics_provider_id"),
        "provider_metrics",
        ["provider_id"],
        unique=False,
    )

    # Add provider_id to tasks table using batch mode for SQLite
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.add_column(sa.Column("provider_id", sa.String(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_provider", "providers", ["provider_id"], ["id"]
        )


def downgrade():
    # Drop foreign key and column from tasks using batch mode for SQLite
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.drop_constraint("fk_tasks_provider", type_="foreignkey")
        batch_op.drop_column("provider_id")

    # Drop provider tables
    op.drop_table("provider_metrics")
    op.drop_table("providers")
