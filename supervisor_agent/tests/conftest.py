import pytest
import tempfile
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from supervisor_agent.db.database import get_db, Base
from supervisor_agent.api.main import app
from supervisor_agent.config import settings


@pytest.fixture(scope="session")
def test_engine():
    """Create a test database engine"""
    # Use in-memory SQLite for tests
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def test_db(test_engine):
    """Create a test database session"""
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def test_client(test_db):
    """Create a test client with database dependency override"""
    def override_get_db():
        try:
            yield test_db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
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
            "diff": "--- a/file.py\n+++ b/file.py\n@@ -1,3 +1,3 @@\n-old line\n+new line"
        },
        "priority": 5
    }


@pytest.fixture
def sample_agent_data():
    """Sample agent data for testing"""
    from datetime import datetime, timedelta
    return {
        "id": "test-agent-1",
        "api_key": "test-api-key",
        "quota_limit": 1000,
        "quota_reset_at": datetime.utcnow() + timedelta(hours=24)
    }