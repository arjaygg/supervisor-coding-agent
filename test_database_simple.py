#!/usr/bin/env python3
"""
Simple database connectivity test
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import sqlite3
from datetime import datetime

def test_sqlite_direct():
    """Test SQLite database directly"""
    try:
        # Connect to database
        conn = sqlite3.connect("supervisor_agent.db")
        cursor = conn.cursor()
        
        print("✅ SQLite connection successful")
        
        # Check tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        table_names = [table[0] for table in tables]
        
        expected_tables = ['agents', 'tasks', 'workflows', 'workflow_executions', 'metrics', 'users', 'providers']
        for table in expected_tables:
            if table in table_names:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"⚠️  Table '{table}' missing")
        
        # Test basic CRUD on existing tables
        print("\n--- Testing Basic CRUD ---")
        
        # Insert test data
        cursor.execute("""
            INSERT INTO agents (id, api_key, quota_limit, quota_reset_at)
            VALUES (?, ?, ?, ?)
        """, ("test-crud-agent", "test-key", 1000, datetime.now().isoformat()))
        
        cursor.execute("""
            INSERT INTO tasks (type, payload, assigned_agent_id)
            VALUES (?, ?, ?)
        """, ("TEST_CRUD", '{"test": "data"}', "test-crud-agent"))
        
        conn.commit()
        print("✅ Test records inserted")
        
        # Read data
        cursor.execute("SELECT COUNT(*) FROM agents WHERE id = 'test-crud-agent'")
        agent_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tasks WHERE type = 'TEST_CRUD'")
        task_count = cursor.fetchone()[0]
        
        print(f"✅ Found {agent_count} test agent(s)")
        print(f"✅ Found {task_count} test task(s)")
        
        # Update data
        cursor.execute("UPDATE tasks SET status = 'COMPLETED' WHERE type = 'TEST_CRUD'")
        print("✅ Task status updated")
        
        # Delete test data
        cursor.execute("DELETE FROM tasks WHERE type = 'TEST_CRUD'")
        cursor.execute("DELETE FROM agents WHERE id = 'test-crud-agent'")
        conn.commit()
        print("✅ Test records deleted")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ SQLite test failed: {e}")
        return False

def test_existing_data():
    """Test reading existing data"""
    try:
        conn = sqlite3.connect("supervisor_agent.db")
        cursor = conn.cursor()
        
        print("\n--- Testing Existing Data ---")
        
        # Count existing records
        cursor.execute("SELECT COUNT(*) FROM providers")
        provider_count = cursor.fetchone()[0]
        print(f"✅ Found {provider_count} existing provider(s)")
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"✅ Found {user_count} existing user(s)")
        
        # List providers
        cursor.execute("SELECT id, name, type FROM providers")
        providers = cursor.fetchall()
        for provider in providers:
            print(f"  - Provider: {provider[0]} ({provider[1]}, {provider[2]})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Existing data test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Testing Database with Simple SQLite Operations\n")
    
    success = True
    success &= test_sqlite_direct()
    success &= test_existing_data()
    
    if success:
        print("\n🎉 All database tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some database tests failed!")
        sys.exit(1)