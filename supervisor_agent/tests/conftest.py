import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from supervisor_agent.api.main import app
from supervisor_agent.config import settings
# Import models to register them with Base
from supervisor_agent.db import models
from supervisor_agent.db.database import Base, get_db


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine"""
    # Use file-based SQLite for tests to avoid threading issues
    db_file = tempfile.NamedTemporaryFile(delete=False)
    db_file.close()
    engine = create_engine(
        f"sqlite:///{db_file.name}",
        echo=False,
        connect_args={
            "check_same_thread": False,  # Allow multiple threads
            "timeout": 20,  # Prevent database locks
        },
        poolclass=None,  # Disable connection pooling for tests
        pool_pre_ping=True,  # Verify connections before use
    )
    Base.metadata.create_all(engine)
    yield engine
    # Cleanup
    engine.dispose()
    try:
        os.unlink(db_file.name)
    except OSError:
        pass


@pytest.fixture
def test_db(test_engine):
    """Create a test database session"""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestSessionLocal()
    try:
        # Test connection before yielding
        db.execute(text("SELECT 1"))
        yield db
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


@pytest.fixture
def test_client(test_engine):
    """Create a test client with database dependency override"""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    def override_get_db():
        db = TestSessionLocal()
        try:
            # Test connection and yield
            db.execute(text("SELECT 1"))
            yield db
        except Exception as e:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Create client with better error handling
    try:
        client = TestClient(app)
        yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def sample_task_data():
    """Sample task data for testing"""
    return {
        "type": "PR_REVIEW",
        "payload": {
            "repository": "test/repo",
            "pr_number": 123,
            "title": "Test PR",
            "description": "A test pull request",
            "diff": "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@\n-old line\n+new line",
        },
        "priority": 5,
    }


@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing"""
    from datetime import datetime, timedelta, timezone

    return {
        "id": "test-agent-1",
        "api_key": "test-api-key",
        "quota_limit": 1000,
        "quota_reset_at": datetime.now(timezone.utc) + timedelta(hours=24),
    }
