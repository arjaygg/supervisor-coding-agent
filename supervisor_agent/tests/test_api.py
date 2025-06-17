import pytest
from fastapi.testclient import TestClient
from supervisor_agent.db import crud, schemas


def test_health_check(test_client):
    """Test health check endpoint"""
    response = test_client.get("/api/v1/healthz")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "timestamp" in data


def test_create_task(test_client, sample_task_data):
    """Test task creation"""
    response = test_client.post("/api/v1/tasks", json=sample_task_data)
    assert response.status_code == 200
    data = response.json()
    assert data["type"] == sample_task_data["type"]
    assert data["payload"] == sample_task_data["payload"]
    assert data["priority"] == sample_task_data["priority"]
    assert "id" in data


def test_get_tasks(test_client, sample_task_data):
    """Test getting tasks"""
    # Create a task first
    create_response = test_client.post("/api/v1/tasks", json=sample_task_data)
    assert create_response.status_code == 200

    # Get tasks
    response = test_client.get("/api/v1/tasks")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1


def test_get_task_by_id(test_client, sample_task_data):
    """Test getting a specific task"""
    # Create a task
    create_response = test_client.post("/api/v1/tasks", json=sample_task_data)
    task_id = create_response.json()["id"]

    # Get the task
    response = test_client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id


def test_get_nonexistent_task(test_client):
    """Test getting a non-existent task"""
    response = test_client.get("/api/v1/tasks/99999")
    assert response.status_code == 404


def test_task_stats(test_client, sample_task_data):
    """Test task statistics endpoint"""
    # Create a task first
    test_client.post("/api/v1/tasks", json=sample_task_data)

    response = test_client.get("/api/v1/tasks/stats/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_tasks" in data
    assert "by_status" in data
    assert "by_type" in data


def test_quota_status(test_client):
    """Test quota status endpoint"""
    response = test_client.get("/api/v1/agents/quota/status")
    assert response.status_code == 200
    data = response.json()
    assert "total_agents" in data
    assert "available_agents" in data


def test_get_agents(test_client):
    """Test getting agents"""
    response = test_client.get("/api/v1/agents")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_audit_logs(test_client, sample_task_data):
    """Test audit logs endpoint"""
    # Create a task to generate audit logs
    test_client.post("/api/v1/tasks", json=sample_task_data)

    response = test_client.get("/api/v1/audit-logs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_detailed_health_check(test_client):
    """Test detailed health check"""
    response = test_client.get("/api/v1/health/detailed")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data
    assert "timestamp" in data


def test_metrics_endpoint(test_client):
    """Test metrics endpoint"""
    response = test_client.get("/api/v1/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "supervisor_agent_tasks_total" in data
    assert "supervisor_agent_agents_total" in data
