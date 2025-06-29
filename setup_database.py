#!/usr/bin/env python3
"""
Simple database setup script for SQLite
Creates essential tables for basic functionality
"""

import sqlite3
import os
from pathlib import Path

# Database file path
DB_PATH = "supervisor_agent.db"

def create_database():
    """Create the SQLite database with essential tables"""
    
    # Remove existing database
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Removed existing database: {DB_PATH}")
    
    # Create new database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Create agents table
        cursor.execute("""
        CREATE TABLE agents (
            id TEXT PRIMARY KEY,
            api_key TEXT NOT NULL,
            quota_used INTEGER DEFAULT 0,
            quota_limit INTEGER NOT NULL,
            quota_reset_at DATETIME NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            last_used_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create tasks table
        cursor.execute("""
        CREATE TABLE tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            payload TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            assigned_agent_id TEXT,
            retry_count INTEGER DEFAULT 0,
            error_message TEXT,
            provider_id TEXT,
            FOREIGN KEY (assigned_agent_id) REFERENCES agents(id)
        )
        """)
        
        # Create workflows table
        cursor.execute("""
        CREATE TABLE workflows (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            definition TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            created_by TEXT
        )
        """)
        
        # Create workflow_executions table
        cursor.execute("""
        CREATE TABLE workflow_executions (
            id TEXT PRIMARY KEY,
            workflow_id TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            input_data TEXT,
            output_data TEXT,
            error_details TEXT,
            started_at DATETIME,
            completed_at DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            triggered_by TEXT,
            FOREIGN KEY (workflow_id) REFERENCES workflows(id)
        )
        """)
        
        # Create metrics table
        cursor.execute("""
        CREATE TABLE metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            metric_type TEXT NOT NULL,
            timestamp DATETIME NOT NULL,
            value REAL NOT NULL,
            string_value TEXT,
            labels TEXT NOT NULL,
            metadata TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create users table
        cursor.execute("""
        CREATE TABLE users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            full_name TEXT,
            password_hash TEXT,
            is_active BOOLEAN DEFAULT 1,
            is_superuser BOOLEAN DEFAULT 0,
            is_verified BOOLEAN DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME,
            disabled_at DATETIME
        )
        """)
        
        # Create providers table
        cursor.execute("""
        CREATE TABLE providers (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            config TEXT NOT NULL,
            is_enabled BOOLEAN DEFAULT 1,
            is_healthy BOOLEAN DEFAULT 1,
            priority INTEGER DEFAULT 1,
            capabilities TEXT,
            rate_limits TEXT,
            last_health_check DATETIME,
            failure_count INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME
        )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX idx_tasks_status ON tasks(status)")
        cursor.execute("CREATE INDEX idx_tasks_created_at ON tasks(created_at)")
        cursor.execute("CREATE INDEX idx_metrics_type ON metrics(metric_type)")
        cursor.execute("CREATE INDEX idx_metrics_timestamp ON metrics(timestamp)")
        cursor.execute("CREATE INDEX idx_providers_type ON providers(type)")
        
        # Commit changes
        conn.commit()
        print(f"Database created successfully: {DB_PATH}")
        print("Created tables: agents, tasks, workflows, workflow_executions, metrics, users, providers")
        
        # Insert a test provider
        cursor.execute("""
        INSERT INTO providers (id, name, type, config, capabilities)
        VALUES (
            'local-mock',
            'Local Mock Provider',
            'local_mock',
            '{"response_delay_min": 0.5, "response_delay_max": 2.0}',
            '{"supported_tasks": ["code_review", "feature_development"]}'
        )
        """)
        
        # Insert a test user
        cursor.execute("""
        INSERT INTO users (id, username, email, full_name)
        VALUES (
            'test-user',
            'testuser',
            'test@example.com',
            'Test User'
        )
        """)
        
        conn.commit()
        print("Inserted test data: 1 provider, 1 user")
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    create_database()