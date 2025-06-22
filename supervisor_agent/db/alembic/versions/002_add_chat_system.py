"""Add chat system tables and relationships

Revision ID: 002_chat_system
Revises: 001_analytics
Create Date: 2025-06-22 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID
import uuid

# Define GUID type for cross-database compatibility
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(value)
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

# revision identifiers, used by Alembic.
revision = '002_chat_system'
down_revision = '001_analytics'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create new enums for chat system (SQLite uses VARCHAR with constraints)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        chatthreadstatus_enum = sa.Enum('ACTIVE', 'ARCHIVED', 'COMPLETED', name='chatthreadstatus')
        chatthreadstatus_enum.create(bind)
        
        messagerole_enum = sa.Enum('USER', 'ASSISTANT', 'SYSTEM', name='messagerole')
        messagerole_enum.create(bind)
        
        messagetype_enum = sa.Enum('TEXT', 'TASK_BREAKDOWN', 'PROGRESS', 'NOTIFICATION', 'ERROR', name='messagetype')
        messagetype_enum.create(bind)
        
        notificationtype_enum = sa.Enum('TASK_COMPLETE', 'TASK_FAILED', 'AGENT_UPDATE', 'SYSTEM_ALERT', name='notificationtype')
        notificationtype_enum.create(bind)
    else:
        # For SQLite, use VARCHAR with check constraints
        chatthreadstatus_enum = sa.String(20)
        messagerole_enum = sa.String(20)
        messagetype_enum = sa.String(20)
        notificationtype_enum = sa.String(20)

    # Create chat_threads table
    op.create_table('chat_threads',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', chatthreadstatus_enum, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_threads_id'), 'chat_threads', ['id'], unique=False)
    op.create_index('ix_chat_threads_status_updated', 'chat_threads', ['status', 'updated_at'], unique=False)
    op.create_index('ix_chat_threads_user_status', 'chat_threads', ['user_id', 'status'], unique=False)

    # Create chat_messages table
    op.create_table('chat_messages',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('thread_id', GUID(), nullable=False),
        sa.Column('role', messagerole_enum, nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('message_type', messagetype_enum, nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('parent_message_id', GUID(), nullable=True),
        sa.ForeignKeyConstraint(['parent_message_id'], ['chat_messages.id'], ),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    op.create_index('ix_chat_messages_thread_created', 'chat_messages', ['thread_id', 'created_at'], unique=False)
    op.create_index('ix_chat_messages_role_type', 'chat_messages', ['role', 'message_type'], unique=False)

    # Create chat_notifications table
    op.create_table('chat_notifications',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('thread_id', GUID(), nullable=False),
        sa.Column('type', notificationtype_enum, nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text("(datetime('now'))"), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['thread_id'], ['chat_threads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_chat_notifications_id'), 'chat_notifications', ['id'], unique=False)
    op.create_index('ix_chat_notifications_thread_unread', 'chat_notifications', ['thread_id', 'is_read'], unique=False)
    op.create_index('ix_chat_notifications_type_created', 'chat_notifications', ['type', 'created_at'], unique=False)

    # Add chat system columns to tasks table (SQLite doesn't support adding foreign keys after table creation)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.add_column('tasks', sa.Column('chat_thread_id', GUID(), nullable=True))
        op.add_column('tasks', sa.Column('source_message_id', GUID(), nullable=True))
        
        # Add foreign key constraints for PostgreSQL
        op.create_foreign_key('fk_tasks_chat_thread', 'tasks', 'chat_threads', ['chat_thread_id'], ['id'])
        op.create_foreign_key('fk_tasks_source_message', 'tasks', 'chat_messages', ['source_message_id'], ['id'])
    else:
        # For SQLite, need to use batch mode for ALTER TABLE with foreign keys
        with op.batch_alter_table('tasks') as batch_op:
            batch_op.add_column(sa.Column('chat_thread_id', GUID(), nullable=True))
            batch_op.add_column(sa.Column('source_message_id', GUID(), nullable=True))


def downgrade() -> None:
    # Remove foreign key constraints and columns from tasks table
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.drop_constraint('fk_tasks_source_message', 'tasks', type_='foreignkey')
        op.drop_constraint('fk_tasks_chat_thread', 'tasks', type_='foreignkey')
        
        # Remove columns from tasks table
        op.drop_column('tasks', 'source_message_id')
        op.drop_column('tasks', 'chat_thread_id')
    else:
        # For SQLite, use batch mode
        with op.batch_alter_table('tasks') as batch_op:
            batch_op.drop_column('source_message_id')
            batch_op.drop_column('chat_thread_id')
    
    # Drop chat tables (in reverse order due to dependencies)
    op.drop_table('chat_notifications')
    op.drop_table('chat_messages')
    op.drop_table('chat_threads')
    
    # Drop enums (only for PostgreSQL)
    bind = op.get_bind()
    if bind.dialect.name == 'postgresql':
        op.execute('DROP TYPE IF EXISTS notificationtype')
        op.execute('DROP TYPE IF EXISTS messagetype')
        op.execute('DROP TYPE IF EXISTS messagerole')
        op.execute('DROP TYPE IF EXISTS chatthreadstatus')