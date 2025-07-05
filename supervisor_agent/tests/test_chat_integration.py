import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from supervisor_agent.api.main import app
from supervisor_agent.db.database import Base, get_db
from supervisor_agent.db.models import ChatMessage, ChatThread

# Create test database
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_chat.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(
    autocommit=False, autoflush=False, bind=engine
)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    # Create test database tables
    Base.metadata.create_all(bind=engine)

    with TestClient(app) as test_client:
        yield test_client

    # Clean up
    Base.metadata.drop_all(bind=engine)


class TestChatIntegration:
    """Integration tests for chat system functionality"""

    def test_create_chat_thread(self, client):
        """Test creating a chat thread"""
        thread_data = {
            "title": "Test Chat Thread",
            "description": "A test chat thread for integration testing",
        }

        response = client.post("/api/v1/chat/threads", json=thread_data)
        assert response.status_code == 200

        data = response.json()
        assert data["title"] == thread_data["title"]
        assert data["description"] == thread_data["description"]
        assert "id" in data
        assert "created_at" in data

    def test_get_chat_threads(self, client):
        """Test retrieving chat threads"""
        # Create a test thread first
        thread_data = {
            "title": "Test Thread for Retrieval",
            "description": "Test description",
        }
        create_response = client.post("/api/v1/chat/threads", json=thread_data)
        assert create_response.status_code == 200

        # Get all threads
        response = client.get("/api/v1/chat/threads")
        assert response.status_code == 200

        data = response.json()
        assert "threads" in data
        assert "total_count" in data
        assert len(data["threads"]) >= 1
        assert any(
            thread["title"] == thread_data["title"]
            for thread in data["threads"]
        )

    def test_send_message_to_thread(self, client):
        """Test sending a message to a chat thread"""
        # Create a test thread first
        thread_data = {
            "title": "Test Thread for Messages",
            "description": "Test description",
        }
        thread_response = client.post("/api/v1/chat/threads", json=thread_data)
        assert thread_response.status_code == 200
        thread_id = thread_response.json()["id"]

        # Send a message
        message_data = {"content": "Hello, this is a test message!"}

        response = client.post(
            f"/api/v1/chat/threads/{thread_id}/messages", json=message_data
        )
        assert response.status_code == 200

        data = response.json()
        assert data["content"] == message_data["content"]
        assert data["role"] == "USER"  # Default role
        assert data["thread_id"] == thread_id
        assert "id" in data
        assert "created_at" in data

    def test_get_thread_messages(self, client):
        """Test retrieving messages from a thread"""
        # Create thread and message
        thread_data = {"title": "Test Thread", "description": "Test"}
        thread_response = client.post("/api/v1/chat/threads", json=thread_data)
        thread_id = thread_response.json()["id"]

        message_data = {"content": "Test message"}
        client.post(
            f"/api/v1/chat/threads/{thread_id}/messages", json=message_data
        )

        # Get messages
        response = client.get(f"/api/v1/chat/threads/{thread_id}/messages")
        assert response.status_code == 200

        data = response.json()
        assert "messages" in data
        assert "has_more" in data
        assert "total_count" in data
        assert len(data["messages"]) >= 1
        assert data["messages"][0]["content"] == message_data["content"]

    def test_chat_thread_with_initial_message(self, client):
        """Test creating a chat thread with an initial message"""
        thread_data = {
            "title": "Thread with Initial Message",
            "description": "Test description",
            "initial_message": "This is the initial message",
        }

        response = client.post("/api/v1/chat/threads", json=thread_data)
        assert response.status_code == 200

        thread_data_response = response.json()
        thread_id = thread_data_response["id"]

        # Check that the initial message was created
        messages_response = client.get(
            f"/api/v1/chat/threads/{thread_id}/messages"
        )
        assert messages_response.status_code == 200

        messages_data = messages_response.json()
        assert "messages" in messages_data
        messages = messages_data["messages"]
        assert len(messages) == 1
        assert messages[0]["content"] == "This is the initial message"
        assert messages[0]["role"] == "USER"

    def test_health_check(self, client):
        """Test API health check"""
        response = client.get("/api/v1/ping")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert data["status"] == "ok"

    def test_chat_api_endpoints_exist(self, client):
        """Test that chat API endpoints are properly registered"""
        # Test that the chat router is properly mounted
        response = client.get("/api/v1/chat/threads")
        assert response.status_code == 200

        # Test non-existent thread
        response = client.get(
            "/api/v1/chat/threads/00000000-0000-0000-0000-000000000000"
        )
        assert response.status_code == 404
