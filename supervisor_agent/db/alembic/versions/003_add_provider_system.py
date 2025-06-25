"""Add provider system tables

Revision ID: 003
Revises: 002
Create Date: 2024-06-24 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '003_provider_system'
down_revision = '002_chat_system'
branch_labels = None
depends_on = None


def upgrade():
    # Create provider_type enum
    provider_type_enum = postgresql.ENUM(
        'claude_cli', 'local_mock', 'openai', 'anthropic_api', 'custom',
        name='providertype'
    )
    provider_type_enum.create(op.get_bind())
    
    # Create provider_status enum
    provider_status_enum = postgresql.ENUM(
        'active', 'inactive', 'degraded', 'maintenance', 'error',
        name='providerstatus'
    )
    provider_status_enum.create(op.get_bind())
    
    # Create providers table
    op.create_table('providers',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('type', provider_type_enum, nullable=False),
        sa.Column('status', provider_status_enum, nullable=True),
        sa.Column('priority', sa.Integer(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=False),
        sa.Column('capabilities', sa.JSON(), nullable=False),
        sa.Column('max_concurrent_requests', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_minute', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_hour', sa.Integer(), nullable=True),
        sa.Column('rate_limit_per_day', sa.Integer(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_health_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('health_status', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_providers_id'), 'providers', ['id'], unique=False)
    op.create_index('ix_providers_type_status', 'providers', ['type', 'status'], unique=False)
    op.create_index('ix_providers_priority_enabled', 'providers', ['priority', 'is_enabled'], unique=False)

    # Create provider_usage table
    op.create_table('provider_usage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider_id', sa.String(), nullable=False),
        sa.Column('task_id', sa.Integer(), nullable=True),
        sa.Column('request_id', sa.String(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False),
        sa.Column('cost_usd', sa.String(), nullable=False),
        sa.Column('execution_time_ms', sa.Integer(), nullable=False),
        sa.Column('model_used', sa.String(), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['provider_id'], ['providers.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_provider_usage_id'), 'provider_usage', ['id'], unique=False)
    op.create_index('ix_provider_usage_provider_timestamp', 'provider_usage', ['provider_id', 'timestamp'], unique=False)
    op.create_index('ix_provider_usage_task_provider', 'provider_usage', ['task_id', 'provider_id'], unique=False)
    op.create_index('ix_provider_usage_success_timestamp', 'provider_usage', ['success', 'timestamp'], unique=False)

    # Add assigned_provider_id column to tasks table
    op.add_column('tasks', sa.Column('assigned_provider_id', sa.String(), nullable=True))
    op.create_foreign_key(None, 'tasks', 'providers', ['assigned_provider_id'], ['id'])


def downgrade():
    # Remove foreign key and column from tasks
    op.drop_constraint(None, 'tasks', type_='foreignkey')
    op.drop_column('tasks', 'assigned_provider_id')
    
    # Drop tables
    op.drop_index('ix_provider_usage_success_timestamp', table_name='provider_usage')
    op.drop_index('ix_provider_usage_task_provider', table_name='provider_usage')
    op.drop_index('ix_provider_usage_provider_timestamp', table_name='provider_usage')
    op.drop_index(op.f('ix_provider_usage_id'), table_name='provider_usage')
    op.drop_table('provider_usage')
    
    op.drop_index('ix_providers_priority_enabled', table_name='providers')
    op.drop_index('ix_providers_type_status', table_name='providers')
    op.drop_index(op.f('ix_providers_id'), table_name='providers')
    op.drop_table('providers')
    
    # Drop enums
    postgresql.ENUM(name='providerstatus').drop(op.get_bind())
    postgresql.ENUM(name='providertype').drop(op.get_bind())