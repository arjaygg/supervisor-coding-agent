"""Add analytics tables

Revision ID: 001_analytics
Revises:
Create Date: 2025-06-21 20:31:30.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "001_analytics"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create agents table first (referenced by tasks)
    op.create_table(
        "agents",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("api_key", sa.String(), nullable=False),
        sa.Column("quota_used", sa.Integer(), nullable=True, default=0),
        sa.Column("quota_limit", sa.Integer(), nullable=False),
        sa.Column("quota_reset_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_agents_id"), "agents", ["id"], unique=False)

    # Create tasks table
    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True, default="PENDING"),
        sa.Column("payload", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=True, default=1),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_agent_id", sa.String(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=True, default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_agent_id"],
            ["agents.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tasks_id"), "tasks", ["id"], unique=False)

    # Create task_sessions table
    op.create_table(
        "task_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("response", sa.Text(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("execution_time_seconds", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["tasks.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create workflows table
    op.create_table(
        "workflows",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("definition", sa.Text(), nullable=False),  # JSON as TEXT
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create workflow_executions table
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("workflow_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=True, default="PENDING"),
        sa.Column("input_data", sa.Text(), nullable=True),  # JSON as TEXT
        sa.Column("output_data", sa.Text(), nullable=True),  # JSON as TEXT
        sa.Column("error_details", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("triggered_by", sa.String(), nullable=True),
        sa.ForeignKeyConstraint(
            ["workflow_id"],
            ["workflows.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create metrics table
    op.create_table(
        "metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("metric_type", sa.String(), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("string_value", sa.String(), nullable=True),
        sa.Column("labels", sa.Text(), nullable=False),  # JSON as TEXT
        sa.Column("metadata", sa.Text(), nullable=False),  # JSON as TEXT
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_metrics_id"), "metrics", ["id"], unique=False)
    op.create_index(
        op.f("ix_metrics_metric_type"), "metrics", ["metric_type"], unique=False
    )
    op.create_index(
        op.f("ix_metrics_timestamp"), "metrics", ["timestamp"], unique=False
    )


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("metrics")
    op.drop_table("workflow_executions")
    op.drop_table("workflows")
    op.drop_table("task_sessions")
    op.drop_table("tasks")
    op.drop_table("agents")
