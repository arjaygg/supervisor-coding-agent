"""Add analytics tables

Revision ID: 001_analytics
Revises: 
Create Date: 2025-06-21 20:31:30.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001_analytics'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create tasks table
    op.create_table('tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.Enum('PR_REVIEW', 'ISSUE_SUMMARY', 'CODE_ANALYSIS', 'REFACTOR', 'BUG_FIX', 'FEATURE', name='tasktype'), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'QUEUED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'RETRY', name='taskstatus'), nullable=True),
    sa.Column('payload', sa.JSON(), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('assigned_agent_id', sa.String(), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['assigned_agent_id'], ['agents.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tasks_id'), 'tasks', ['id'], unique=False)

    # Create agents table
    op.create_table('agents',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('api_key', sa.String(), nullable=False),
    sa.Column('quota_used', sa.Integer(), nullable=True),
    sa.Column('quota_limit', sa.Integer(), nullable=False),
    sa.Column('quota_reset_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agents_id'), 'agents', ['id'], unique=False)

    # Create task_sessions table
    op.create_table('task_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('prompt', sa.Text(), nullable=False),
    sa.Column('response', sa.Text(), nullable=True),
    sa.Column('result', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('execution_time_seconds', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create audit_logs table
    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(), nullable=False),
    sa.Column('agent_id', sa.String(), nullable=True),
    sa.Column('task_id', sa.Integer(), nullable=True),
    sa.Column('prompt_hash', sa.String(), nullable=True),
    sa.Column('details', sa.JSON(), nullable=True),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('ip_address', sa.String(), nullable=True),
    sa.Column('user_agent', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_audit_logs_id'), 'audit_logs', ['id'], unique=False)

    # Create cost_tracking table
    op.create_table('cost_tracking',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=False),
    sa.Column('agent_id', sa.String(), nullable=False),
    sa.Column('prompt_tokens', sa.Integer(), nullable=False),
    sa.Column('completion_tokens', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('estimated_cost_usd', sa.String(), nullable=False),
    sa.Column('model_used', sa.String(), nullable=True),
    sa.Column('execution_time_ms', sa.Integer(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['agent_id'], ['agents.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create usage_metrics table
    op.create_table('usage_metrics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('metric_type', sa.String(), nullable=False),
    sa.Column('metric_key', sa.String(), nullable=False),
    sa.Column('total_requests', sa.Integer(), nullable=False),
    sa.Column('total_tokens', sa.Integer(), nullable=False),
    sa.Column('total_cost_usd', sa.String(), nullable=False),
    sa.Column('avg_response_time_ms', sa.Integer(), nullable=False),
    sa.Column('success_rate', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_usage_metrics_id'), 'usage_metrics', ['id'], unique=False)

    # Create workflow tables
    op.create_table('workflows',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('definition', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('workflow_executions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workflow_id', sa.String(), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='workflowstatus'), nullable=True),
    sa.Column('input_data', sa.JSON(), nullable=True),
    sa.Column('output_data', sa.JSON(), nullable=True),
    sa.Column('error_details', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('triggered_by', sa.String(), nullable=True),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('workflow_task_executions',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('execution_id', sa.String(), nullable=False),
    sa.Column('task_name', sa.String(), nullable=False),
    sa.Column('task_id', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED', name='workflowtaskstatus'), nullable=True),
    sa.Column('input_data', sa.JSON(), nullable=True),
    sa.Column('output_data', sa.JSON(), nullable=True),
    sa.Column('error_details', sa.Text(), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('retry_count', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['execution_id'], ['workflow_executions.id'], ),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('task_dependencies',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('workflow_id', sa.String(), nullable=False),
    sa.Column('dependent_task', sa.String(), nullable=False),
    sa.Column('prerequisite_task', sa.String(), nullable=False),
    sa.Column('dependency_type', sa.Enum('SEQUENCE', 'SUCCESS', 'FAILURE', 'ALWAYS', name='dependencytype'), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('workflow_schedules',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('workflow_id', sa.String(), nullable=False),
    sa.Column('cron_expression', sa.String(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['workflow_id'], ['workflows.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    # Create analytics tables
    op.create_table('metrics',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('metric_type', sa.String(), nullable=False),
    sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('string_value', sa.String(), nullable=True),
    sa.Column('labels', sa.JSON(), nullable=False),
    sa.Column('metadata', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_metrics_id'), 'metrics', ['id'], unique=False)
    op.create_index(op.f('ix_metrics_metric_type'), 'metrics', ['metric_type'], unique=False)
    op.create_index(op.f('ix_metrics_timestamp'), 'metrics', ['timestamp'], unique=False)

    op.create_table('dashboards',
    sa.Column('id', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('config', sa.JSON(), nullable=False),
    sa.Column('created_by', sa.String(), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_dashboards_id'), 'dashboards', ['id'], unique=False)

    op.create_table('analytics_cache',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('query_hash', sa.String(), nullable=False),
    sa.Column('query_config', sa.JSON(), nullable=False),
    sa.Column('result_data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('hit_count', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('query_hash')
    )
    op.create_index(op.f('ix_analytics_cache_id'), 'analytics_cache', ['id'], unique=False)
    op.create_index(op.f('ix_analytics_cache_query_hash'), 'analytics_cache', ['query_hash'], unique=True)
    op.create_index(op.f('ix_analytics_cache_expires_at'), 'analytics_cache', ['expires_at'], unique=False)

    op.create_table('alert_rules',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('metric_type', sa.String(), nullable=False),
    sa.Column('condition', sa.String(), nullable=False),
    sa.Column('threshold', sa.Float(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('notification_config', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.Column('last_triggered', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_alert_rules_id'), 'alert_rules', ['id'], unique=False)


def downgrade() -> None:
    # Drop analytics tables
    op.drop_table('alert_rules')
    op.drop_table('analytics_cache')
    op.drop_table('dashboards')
    op.drop_table('metrics')
    
    # Drop workflow tables
    op.drop_table('workflow_schedules')
    op.drop_table('task_dependencies')
    op.drop_table('workflow_task_executions')
    op.drop_table('workflow_executions')
    op.drop_table('workflows')
    
    # Drop existing tables
    op.drop_table('usage_metrics')
    op.drop_table('cost_tracking')
    op.drop_table('audit_logs')
    op.drop_table('task_sessions')
    op.drop_table('tasks')
    op.drop_table('agents')
    
    # Drop enums
    op.execute('DROP TYPE IF EXISTS tasktype')
    op.execute('DROP TYPE IF EXISTS taskstatus')
    op.execute('DROP TYPE IF EXISTS workflowstatus')
    op.execute('DROP TYPE IF EXISTS workflowtaskstatus')
    op.execute('DROP TYPE IF EXISTS dependencytype')