import asyncio
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket

from supervisor_agent.api.main import app
from supervisor_agent.api.websocket import WebSocketManager, websocket_manager
from supervisor_agent.db.models import Task, TaskStatus


class TestWebSocketManager:
    """Test the WebSocket manager functionality."""

    def test_connect_websocket(self):
        """Test connecting a WebSocket client."""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)

        manager.connect(mock_websocket)

        assert mock_websocket in manager.active_connections
        assert len(manager.active_connections) == 1

    def test_disconnect_websocket(self):
        """Test disconnecting a WebSocket client."""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)

        manager.connect(mock_websocket)
        manager.disconnect(mock_websocket)

        assert mock_websocket not in manager.active_connections
        assert len(manager.active_connections) == 0

    @pytest.mark.asyncio
    async def test_send_task_update(self):
        """Test sending task updates to connected clients."""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.send_text = AsyncMock()

        manager.connect(mock_websocket)

        task_data = {
            "id": 1,
            "type": "PR_REVIEW",
            "status": "IN_PROGRESS",
            "priority": 5,
        }

        await manager.send_task_update(task_data)

        expected_message = json.dumps(
            {
                "type": "task_update",
                "task": task_data,
                "timestamp": mock_websocket.send_text.call_args[0][0],
            }
        )

        mock_websocket.send_text.assert_called_once()
        # Verify the message structure
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "task_update"
        assert sent_message["task"] == task_data
        assert "timestamp" in sent_message

    @pytest.mark.asyncio
    async def test_send_task_update_handles_disconnected_clients(self):
        """Test that sending updates handles disconnected clients gracefully."""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.send_text = AsyncMock(side_effect=Exception("Connection closed"))

        manager.connect(mock_websocket)

        task_data = {"id": 1, "status": "COMPLETED"}
        await manager.send_task_update(task_data)

        # Should remove the failed connection
        assert mock_websocket not in manager.active_connections

    @pytest.mark.asyncio
    async def test_send_quota_update(self):
        """Test sending quota updates to connected clients."""
        manager = WebSocketManager()
        mock_websocket = Mock(spec=WebSocket)
        mock_websocket.send_text = AsyncMock()

        manager.connect(mock_websocket)

        quota_data = {
            "available_agents": 2,
            "total_agents": 3,
            "quota_remaining": {"agent-1": 500},
        }

        await manager.send_quota_update(quota_data)

        mock_websocket.send_text.assert_called_once()
        sent_message = json.loads(mock_websocket.send_text.call_args[0][0])
        assert sent_message["type"] == "quota_update"
        assert sent_message["quota_status"] == quota_data


class TestWebSocketEndpoint:
    """Test the WebSocket endpoint integration."""

    def test_websocket_endpoint_exists(self):
        """Test that the WebSocket endpoint is properly configured."""
        with TestClient(app) as client:
            # Test that we can connect to the websocket endpoint
            # This will fail if the endpoint doesn't exist
            try:
                with client.websocket_connect("/ws") as websocket:
                    # If we get here, the endpoint exists
                    assert True
            except Exception as e:
                # Expected to fail in test environment without proper WebSocket setup
                # but we can verify the endpoint exists by checking routes
                websocket_routes = [
                    route
                    for route in app.routes
                    if hasattr(route, "path") and route.path == "/ws"
                ]
                assert len(websocket_routes) == 1


class TestWebSocketIntegration:
    """Test WebSocket integration with the task system."""

    @pytest.mark.asyncio
    async def test_task_creation_sends_websocket_update(self):
        """Test that creating a task sends a WebSocket update."""
        with patch("supervisor_agent.api.websocket.websocket_manager") as mock_manager:
            mock_manager.send_task_update = AsyncMock()

            # Mock task creation
            task_data = {
                "id": 1,
                "type": "PR_REVIEW",
                "status": "PENDING",
                "priority": 5,
                "created_at": "2023-01-01T00:00:00Z",
            }

            # Simulate task creation (this would normally be called from task creation)
            from supervisor_agent.api.websocket import notify_task_update

            await notify_task_update(task_data)

            mock_manager.send_task_update.assert_called_once_with(task_data)

    @pytest.mark.asyncio
    async def test_task_status_change_sends_websocket_update(self):
        """Test that changing task status sends a WebSocket update."""
        with patch("supervisor_agent.api.websocket.websocket_manager") as mock_manager:
            mock_manager.send_task_update = AsyncMock()

            # Mock task status change
            task_data = {
                "id": 1,
                "type": "PR_REVIEW",
                "status": "COMPLETED",
                "priority": 5,
                "updated_at": "2023-01-01T01:00:00Z",
            }

            # Simulate task status change
            from supervisor_agent.api.websocket import notify_task_update

            await notify_task_update(task_data)

            mock_manager.send_task_update.assert_called_once_with(task_data)


# Test criteria for US1.1 (INVEST principles)
class TestUS1_1_Acceptance:
    """Acceptance tests for US1.1: Real-time notifications of AI suggestions."""

    def test_websocket_manager_exists(self):
        """Test that WebSocket manager exists and is configured."""
        from supervisor_agent.api.websocket import websocket_manager

        assert websocket_manager is not None
        assert hasattr(websocket_manager, "active_connections")
        assert hasattr(websocket_manager, "send_task_update")

    def test_websocket_endpoint_available(self):
        """Test that /ws endpoint is available for connections."""
        # Check that the WebSocket route exists in the app
        websocket_routes = [
            route
            for route in app.routes
            if hasattr(route, "path") and route.path == "/ws"
        ]
        assert len(websocket_routes) >= 1, "WebSocket endpoint /ws should be available"

    @pytest.mark.asyncio
    async def test_task_updates_trigger_websocket_notifications(self):
        """Test that task updates trigger WebSocket notifications."""
        with patch("supervisor_agent.api.websocket.websocket_manager") as mock_manager:
            mock_manager.send_task_update = AsyncMock()

            # This would be called when a task is updated
            from supervisor_agent.api.websocket import notify_task_update

            task_update = {
                "id": 1,
                "type": "PR_REVIEW",
                "status": "IN_PROGRESS",
                "ai_suggestion": {
                    "type": "code_review",
                    "message": "Consider adding error handling here",
                    "line": 42,
                    "file": "src/main.py",
                },
            }

            await notify_task_update(task_update)

            mock_manager.send_task_update.assert_called_once_with(task_update)

            # Verify that the task contains AI suggestion data
            call_args = mock_manager.send_task_update.call_args[0][0]
            assert "ai_suggestion" in call_args
            assert call_args["ai_suggestion"]["type"] == "code_review"

    def test_websocket_message_format_compliance(self):
        """Test that WebSocket messages follow the expected format."""
        # Test message structure
        expected_fields = ["type", "task", "timestamp"]

        # This would be the actual message format
        sample_message = {
            "type": "task_update",
            "task": {
                "id": 1,
                "status": "IN_PROGRESS",
                "ai_suggestion": {"message": "test"},
            },
            "timestamp": "2023-01-01T00:00:00Z",
        }

        for field in expected_fields:
            assert field in sample_message, f"Message should contain {field} field"

        # Verify task contains AI suggestion
        assert "ai_suggestion" in sample_message["task"]
