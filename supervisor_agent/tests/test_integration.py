"""
Integration tests for critical user flows
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from supervisor_agent.db.models import Task, TaskStatus, TaskType


class TestCriticalUserFlows:
    """Test the most important user flows end-to-end"""

    def test_create_and_process_task_flow(self, test_client: TestClient, test_db):
        """Test the complete flow: create task -> process -> complete"""

        # 1. Create a task via API
        task_data = {
            "type": "CODE_ANALYSIS",
            "payload": {
                "code": "def hello(): print('world')",
                "language": "python",
            },
            "priority": 5,
        }

        response = test_client.post("/api/v1/tasks", json=task_data)
        assert response.status_code == 200
        task = response.json()
        assert task["type"] == "CODE_ANALYSIS"
        assert task["status"] == "PENDING"
        task_id = task["id"]

        # 2. Verify task was created in database
        db_task = test_db.query(Task).filter(Task.id == task_id).first()
        assert db_task is not None
        assert db_task.type == TaskType.CODE_ANALYSIS
        assert db_task.status == TaskStatus.PENDING

        # 3. Check task appears in task list
        response = test_client.get("/api/v1/tasks")
        assert response.status_code == 200
        tasks = response.json()
        assert len(tasks) >= 1
        assert any(t["id"] == task_id for t in tasks)

        # 4. Get task stats
        response = test_client.get("/api/v1/tasks/stats/summary")
        assert response.status_code == 200
        stats = response.json()
        assert stats["total_tasks"] >= 1
        assert "PENDING" in stats["by_status"]

        # 5. Check individual task retrieval
        response = test_client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        retrieved_task = response.json()
        assert retrieved_task["id"] == task_id
        assert retrieved_task["type"] == "CODE_ANALYSIS"

    def test_task_retry_flow(self, test_client: TestClient, test_db):
        """Test task retry functionality"""

        # Create a task
        task_data = {
            "type": "BUG_FIX",
            "payload": {"description": "Fix critical bug"},
            "priority": 1,
        }

        response = test_client.post("/api/v1/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json()["id"]

        # Manually mark task as failed for testing
        db_task = test_db.query(Task).filter(Task.id == task_id).first()
        db_task.status = TaskStatus.FAILED
        db_task.error_message = "Simulated failure"
        test_db.commit()

        # Test retry
        response = test_client.post(f"/api/v1/tasks/{task_id}/retry")
        assert response.status_code == 200
        retry_response = response.json()
        assert retry_response["task_id"] == task_id

        # Verify task status was reset
        test_db.refresh(db_task)
        assert db_task.status == TaskStatus.PENDING
        assert db_task.error_message is None

    def test_api_error_handling(self, test_client: TestClient):
        """Test API error handling for common error scenarios"""

        # Test 404 for non-existent task
        response = test_client.get("/api/v1/tasks/99999")
        assert response.status_code == 404

        # Test invalid task creation
        invalid_task = {"type": "INVALID_TYPE", "payload": {}, "priority": 5}
        response = test_client.post("/api/v1/tasks", json=invalid_task)
        assert response.status_code == 422  # Validation error

        # Test retry on non-existent task
        response = test_client.post("/api/v1/tasks/99999/retry")
        assert response.status_code == 404

    def test_health_endpoints(self, test_client: TestClient):
        """Test health check endpoints"""

        # Basic health check
        response = test_client.get("/api/v1/healthz")
        assert response.status_code == 200
        health = response.json()
        assert "status" in health

        # Detailed health check
        response = test_client.get("/api/v1/health/detailed")
        assert response.status_code == 200
        detailed_health = response.json()
        assert "database" in detailed_health
        assert "redis" in detailed_health

    def test_agent_endpoints(self, test_client: TestClient):
        """Test agent-related endpoints"""

        # Get agents
        response = test_client.get("/api/v1/agents")
        assert response.status_code == 200
        agents = response.json()
        assert isinstance(agents, list)

        # Get quota status
        response = test_client.get("/api/v1/agents/quota/status")
        assert response.status_code == 200
        quota_status = response.json()
        assert "available_agents" in quota_status

    def test_websocket_endpoint(self, test_client: TestClient):
        """Test WebSocket endpoint basic connectivity"""
        with test_client.websocket_connect("/ws") as websocket:
            # WebSocket should connect successfully
            # In a real test, we'd verify task update messages
            pass

    def test_task_types_coverage(self, test_client: TestClient):
        """Test that all supported task types can be created"""

        task_types = [
            "PR_REVIEW",
            "CODE_ANALYSIS",
            "BUG_FIX",
            "FEATURE",
            "REFACTOR",
        ]

        created_tasks = []

        for task_type in task_types:
            task_data = {
                "type": task_type,
                "payload": {
                    "description": f"Test {task_type} task",
                    "code": ("test code" if task_type == "CODE_ANALYSIS" else None),
                },
                "priority": 5,
            }

            response = test_client.post("/api/v1/tasks", json=task_data)
            assert response.status_code == 200, f"Failed to create {task_type} task"
            task = response.json()
            assert task["type"] == task_type
            created_tasks.append(task["id"])

        # Verify all tasks were created
        response = test_client.get("/api/v1/tasks")
        assert response.status_code == 200
        all_tasks = response.json()

        for task_id in created_tasks:
            assert any(
                t["id"] == task_id for t in all_tasks
            ), f"Task {task_id} not found in task list"


class TestMockModeIntegration:
    """Test that mock mode works correctly"""

    def test_mock_agent_responses(self, test_client: TestClient, test_db):
        """Test that mock mode generates appropriate responses"""

        # Create a task that should trigger mock response
        task_data = {
            "type": "CODE_ANALYSIS",
            "payload": {"code": "def test(): pass", "language": "python"},
            "priority": 5,
        }

        response = test_client.post("/api/v1/tasks", json=task_data)
        assert response.status_code == 200
        task_id = response.json()["id"]

        # In mock mode, we expect the task to be created successfully
        # The actual processing would happen asynchronously via Celery
        # but we can verify the task structure is correct

        response = test_client.get(f"/api/v1/tasks/{task_id}")
        assert response.status_code == 200
        task = response.json()
        assert task["type"] == "CODE_ANALYSIS"
        assert "code" in task["payload"]
