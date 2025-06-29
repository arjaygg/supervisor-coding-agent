#!/usr/bin/env python3
"""
Test database connectivity and CRUD operations
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from supervisor_agent.db.database import SessionLocal
from supervisor_agent.db.models import Task, Agent, Provider, TaskSession
from datetime import datetime, timezone

def test_database_connection():
    """Test basic database connectivity"""
    try:
        db = SessionLocal()
        # Test basic query
        result = db.execute("SELECT 1").fetchone()
        print("✅ Database connection successful")
        db.close()
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False

def test_crud_operations():
    """Test basic CRUD operations"""
    db = SessionLocal()
    
    try:
        # Test CREATE operations
        print("\n--- Testing CREATE operations ---")
        
        # Create test agent
        test_agent = Agent(
            id="test-agent",
            api_key="test-key",
            quota_limit=1000,
            quota_reset_at=datetime.now(timezone.utc)
        )
        db.add(test_agent)
        db.commit()
        print("✅ Agent created successfully")
        
        # Create test task
        test_task = Task(
            type="TEST",
            payload='{"test": "data"}',
            assigned_agent_id="test-agent"
        )
        db.add(test_task)
        db.commit()
        print("✅ Task created successfully")
        
        # Create test task session
        test_session = TaskSession(
            task_id=test_task.id,
            prompt="Test prompt",
            response="Test response"
        )
        db.add(test_session)
        db.commit()
        print("✅ Task session created successfully")
        
        # Create test provider
        test_provider = Provider(
            id="test-provider",
            name="Test Provider",
            type="local_mock",
            config='{"test": "config"}'
        )
        db.add(test_provider)
        db.commit()
        print("✅ Provider created successfully")
        
        # Test READ operations
        print("\n--- Testing READ operations ---")
        
        # Read agents
        agents = db.query(Agent).all()
        print(f"✅ Found {len(agents)} agents")
        
        # Read tasks
        tasks = db.query(Task).all()
        print(f"✅ Found {len(tasks)} tasks")
        
        # Read task sessions
        sessions = db.query(TaskSession).all()
        print(f"✅ Found {len(sessions)} task sessions")
        
        # Read providers
        providers = db.query(Provider).all()
        print(f"✅ Found {len(providers)} providers")
        
        # Test UPDATE operations
        print("\n--- Testing UPDATE operations ---")
        
        # Update task status
        task = db.query(Task).filter(Task.type == "TEST").first()
        if task:
            task.status = "COMPLETED"
            db.commit()
            print("✅ Task updated successfully")
        
        # Test DELETE operations
        print("\n--- Testing DELETE operations ---")
        
        # Delete test records (order matters due to foreign keys)
        db.query(TaskSession).filter(TaskSession.task_id.in_(
            db.query(Task.id).filter(Task.type == "TEST")
        )).delete(synchronize_session=False)
        db.query(Task).filter(Task.type == "TEST").delete()
        db.query(Agent).filter(Agent.id == "test-agent").delete()
        db.query(Provider).filter(Provider.id == "test-provider").delete()
        db.commit()
        print("✅ Test records deleted successfully")
        
        print("\n✅ All CRUD operations completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ CRUD operation failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def test_relationships():
    """Test foreign key relationships"""
    db = SessionLocal()
    
    try:
        print("\n--- Testing Relationships ---")
        
        # Create agent
        agent = Agent(
            id="rel-test-agent",
            api_key="test-key",
            quota_limit=1000,
            quota_reset_at=datetime.now(timezone.utc)
        )
        db.add(agent)
        db.commit()
        
        # Create task with agent relationship
        task = Task(
            type="RELATIONSHIP_TEST",
            payload='{"test": "relationship"}',
            assigned_agent_id="rel-test-agent"
        )
        db.add(task)
        db.commit()
        
        # Test relationship query
        task_with_agent = db.query(Task).filter(Task.id == task.id).first()
        if task_with_agent and task_with_agent.assigned_agent_id == "rel-test-agent":
            print("✅ Foreign key relationship working")
        
        # Cleanup
        db.delete(task)
        db.delete(agent)
        db.commit()
        
        return True
        
    except Exception as e:
        print(f"❌ Relationship test failed: {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    print("🧪 Testing Database Connectivity and CRUD Operations\n")
    
    success = True
    success &= test_database_connection()
    success &= test_crud_operations()
    success &= test_relationships()
    
    if success:
        print("\n🎉 All database tests passed!")
        sys.exit(0)
    else:
        print("\n💥 Some database tests failed!")
        sys.exit(1)