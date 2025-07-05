"""Add authentication and authorization system

Revision ID: 004_add_auth_system
Revises: 003_add_provider_system
Create Date: 2025-01-20 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "004_add_auth_system"
down_revision = "003_add_provider_system"
branch_labels = None
depends_on = None


def upgrade():
    # Add authentication fields to users table using batch mode for SQLite
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(
            sa.Column("password_hash", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "is_superuser", sa.Boolean(), nullable=True, default=False
            )
        )
        batch_op.add_column(
            sa.Column(
                "is_verified", sa.Boolean(), nullable=True, default=False
            )
        )
        batch_op.add_column(
            sa.Column("disabled_at", sa.DateTime(), nullable=True)
        )

    # Create user_sessions table
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("user_agent", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("last_accessed", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_user_sessions_id"), "user_sessions", ["id"], unique=False
    )
    op.create_index(
        op.f("ix_user_sessions_token_hash"),
        "user_sessions",
        ["token_hash"],
        unique=True,
    )

    # Create api_keys table
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("permissions", sa.Text(), nullable=True),  # JSON as TEXT
        sa.Column("is_active", sa.Boolean(), nullable=True, default=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_used", sa.DateTime(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_api_keys_id"), "api_keys", ["id"], unique=False)
    op.create_index(
        op.f("ix_api_keys_key_hash"), "api_keys", ["key_hash"], unique=True
    )


def downgrade():
    # Drop tables
    op.drop_table("api_keys")
    op.drop_table("user_sessions")

    # Remove columns from users table using batch mode for SQLite
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("disabled_at")
        batch_op.drop_column("is_verified")
        batch_op.drop_column("is_superuser")
        batch_op.drop_column("password_hash")
