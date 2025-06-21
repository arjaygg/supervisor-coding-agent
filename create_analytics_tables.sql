-- Create analytics tables for supervisor agent

-- First create necessary enums
CREATE TYPE tasktype AS ENUM ('PR_REVIEW', 'ISSUE_SUMMARY', 'CODE_ANALYSIS', 'REFACTOR', 'BUG_FIX', 'FEATURE');
CREATE TYPE taskstatus AS ENUM ('PENDING', 'QUEUED', 'IN_PROGRESS', 'COMPLETED', 'FAILED', 'RETRY');
CREATE TYPE workflowstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED');
CREATE TYPE workflowtaskstatus AS ENUM ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'SKIPPED');
CREATE TYPE dependencytype AS ENUM ('SEQUENCE', 'SUCCESS', 'FAILURE', 'ALWAYS');

-- Create agents table
CREATE TABLE IF NOT EXISTS agents (
    id VARCHAR PRIMARY KEY,
    api_key VARCHAR NOT NULL,
    quota_used INTEGER DEFAULT 0,
    quota_limit INTEGER NOT NULL,
    quota_reset_at TIMESTAMP WITH TIME ZONE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_used_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_agents_id ON agents (id);

-- Create tasks table
CREATE TABLE IF NOT EXISTS tasks (
    id SERIAL PRIMARY KEY,
    type tasktype NOT NULL,
    status taskstatus DEFAULT 'PENDING',
    payload JSONB NOT NULL,
    priority INTEGER DEFAULT 5,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    assigned_agent_id VARCHAR REFERENCES agents(id),
    retry_count INTEGER DEFAULT 0,
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS ix_tasks_id ON tasks (id);

-- Create task_sessions table
CREATE TABLE IF NOT EXISTS task_sessions (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    prompt TEXT NOT NULL,
    response TEXT,
    result JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    execution_time_seconds INTEGER
);

-- Create audit_logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    event_type VARCHAR NOT NULL,
    agent_id VARCHAR,
    task_id INTEGER,
    prompt_hash VARCHAR,
    details JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now(),
    ip_address VARCHAR,
    user_agent VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_audit_logs_id ON audit_logs (id);

-- Create cost_tracking table
CREATE TABLE IF NOT EXISTS cost_tracking (
    id SERIAL PRIMARY KEY,
    task_id INTEGER NOT NULL REFERENCES tasks(id),
    agent_id VARCHAR NOT NULL REFERENCES agents(id),
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd VARCHAR NOT NULL DEFAULT '0.00',
    model_used VARCHAR,
    execution_time_ms INTEGER NOT NULL DEFAULT 0,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now()
);

-- Create usage_metrics table
CREATE TABLE IF NOT EXISTS usage_metrics (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR NOT NULL,
    metric_key VARCHAR NOT NULL,
    total_requests INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    total_cost_usd VARCHAR NOT NULL DEFAULT '0.00',
    avg_response_time_ms INTEGER NOT NULL DEFAULT 0,
    success_rate VARCHAR NOT NULL DEFAULT '100.00',
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_usage_metrics_id ON usage_metrics (id);

-- Create workflow tables
CREATE TABLE IF NOT EXISTS workflows (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    definition JSONB NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE,
    created_by VARCHAR
);

CREATE TABLE IF NOT EXISTS workflow_executions (
    id VARCHAR PRIMARY KEY,
    workflow_id VARCHAR NOT NULL REFERENCES workflows(id),
    status workflowstatus DEFAULT 'PENDING',
    input_data JSONB,
    output_data JSONB,
    error_details TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    triggered_by VARCHAR
);

CREATE TABLE IF NOT EXISTS workflow_task_executions (
    id VARCHAR PRIMARY KEY,
    execution_id VARCHAR NOT NULL REFERENCES workflow_executions(id),
    task_name VARCHAR NOT NULL,
    task_id INTEGER REFERENCES tasks(id),
    status workflowtaskstatus DEFAULT 'PENDING',
    input_data JSONB,
    output_data JSONB,
    error_details TEXT,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS task_dependencies (
    id SERIAL PRIMARY KEY,
    workflow_id VARCHAR NOT NULL REFERENCES workflows(id),
    dependent_task VARCHAR NOT NULL,
    prerequisite_task VARCHAR NOT NULL,
    dependency_type dependencytype DEFAULT 'SEQUENCE',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS workflow_schedules (
    id VARCHAR PRIMARY KEY,
    workflow_id VARCHAR NOT NULL REFERENCES workflows(id),
    cron_expression VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT true,
    last_run_at TIMESTAMP WITH TIME ZONE,
    next_run_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Create analytics tables
CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    metric_type VARCHAR NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    string_value VARCHAR,
    labels JSONB NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_metrics_id ON metrics (id);
CREATE INDEX IF NOT EXISTS ix_metrics_metric_type ON metrics (metric_type);
CREATE INDEX IF NOT EXISTS ix_metrics_timestamp ON metrics (timestamp);

CREATE TABLE IF NOT EXISTS dashboards (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    config JSONB NOT NULL,
    created_by VARCHAR,
    is_public BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    updated_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_dashboards_id ON dashboards (id);

CREATE TABLE IF NOT EXISTS analytics_cache (
    id SERIAL PRIMARY KEY,
    query_hash VARCHAR NOT NULL UNIQUE,
    query_config JSONB NOT NULL,
    result_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    hit_count INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_analytics_cache_id ON analytics_cache (id);
CREATE INDEX IF NOT EXISTS ix_analytics_cache_query_hash ON analytics_cache (query_hash);
CREATE INDEX IF NOT EXISTS ix_analytics_cache_expires_at ON analytics_cache (expires_at);

CREATE TABLE IF NOT EXISTS alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL,
    description TEXT,
    metric_type VARCHAR NOT NULL,
    condition VARCHAR NOT NULL,
    threshold DOUBLE PRECISION NOT NULL,
    is_active BOOLEAN DEFAULT true,
    notification_config JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now(),
    last_triggered TIMESTAMP WITH TIME ZONE
);
CREATE INDEX IF NOT EXISTS ix_alert_rules_id ON alert_rules (id);

-- Update alembic version
INSERT INTO alembic_version (version_num) VALUES ('001_analytics') 
ON CONFLICT (version_num) DO NOTHING;