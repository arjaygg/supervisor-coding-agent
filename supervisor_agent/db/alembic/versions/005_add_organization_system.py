"""Add organization system (folders, tags, favorites) for conversations

Revision ID: 005_add_organization_system
Revises: 004_add_auth_system
Create Date: 2025-01-22 14:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import CHAR, TypeDecorator

# revision identifiers, used by Alembic.
revision = "005_add_organization_system"
down_revision = "004_add_auth_system"
branch_labels = None
depends_on = None


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL's UUID type, otherwise uses CHAR(36), storing as stringified hex values.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))


def upgrade():
    # Create folders table
    op.create_table(
        "folders",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("parent_id", GUID(), nullable=True),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("position", sa.Integer(), default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["folders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_folders_id"), "folders", ["id"], unique=False)
    op.create_index(op.f("ix_folders_user_id"), "folders", ["user_id"], unique=False)

    # Create tags table
    op.create_table(
        "tags",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("usage_count", sa.Integer(), default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tags_id"), "tags", ["id"], unique=False)
    op.create_index(op.f("ix_tags_name"), "tags", ["name"], unique=True)
    op.create_index(op.f("ix_tags_user_id"), "tags", ["user_id"], unique=False)

    # Create favorites table
    op.create_table(
        "favorites",
        sa.Column("id", GUID(), nullable=False),
        sa.Column("conversation_id", GUID(), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_threads.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_favorites_id"), "favorites", ["id"], unique=False)
    op.create_index(op.f("ix_favorites_user_id"), "favorites", ["user_id"], unique=False)
    op.create_index(op.f("ix_favorites_conversation_id"), "favorites", ["conversation_id"], unique=False)

    # Create conversation_tags association table
    op.create_table(
        "conversation_tags",
        sa.Column("conversation_id", GUID(), nullable=False),
        sa.Column("tag_id", GUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["chat_threads.id"],
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"],
            ["tags.id"],
        ),
        sa.PrimaryKeyConstraint("conversation_id", "tag_id"),
    )

    # Add organization fields to chat_threads table using batch mode for SQLite
    with op.batch_alter_table("chat_threads") as batch_op:
        batch_op.add_column(sa.Column("folder_id", GUID(), nullable=True))
        batch_op.add_column(sa.Column("is_pinned", sa.Boolean(), default=False))
        batch_op.add_column(sa.Column("priority", sa.Integer(), default=0))
        batch_op.create_foreign_key(
            "fk_chat_threads_folder", "folders", ["folder_id"], ["id"]
        )


def downgrade():
    # Remove organization fields from chat_threads table using batch mode for SQLite
    with op.batch_alter_table("chat_threads") as batch_op:
        batch_op.drop_constraint("fk_chat_threads_folder", type_="foreignkey")
        batch_op.drop_column("priority")
        batch_op.drop_column("is_pinned")
        batch_op.drop_column("folder_id")

    # Drop organization tables in reverse order
    op.drop_table("conversation_tags")
    op.drop_table("favorites")
    op.drop_table("tags")
    op.drop_table("folders")