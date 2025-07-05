import json
from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import WebSocket, WebSocketDisconnect

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class WebSocketManager:
    """Manages WebSocket connections and broadcasts."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection."""
        self.active_connections.append(websocket)
        logger.info(
            f"WebSocket connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"WebSocket disconnected. Total connections: {len(self.active_connections)}"
            )

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send a message to a specific WebSocket connection."""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error sending personal message: {e}")
            self.disconnect(websocket)

    async def broadcast(self, message: str):
        """Broadcast a message to all connected WebSocket clients."""
        if not self.active_connections:
            return

        disconnected = []

        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.warning(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def send_task_update(self, task_data: Dict[str, Any]):
        """Send a task update to all connected clients."""
        message = {
            "type": "task_update",
            "task": task_data,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        await self.broadcast(json.dumps(message))
        logger.debug(
            f"Sent task update for task {task_data.get('id', 'unknown')}"
        )

    async def send_quota_update(self, quota_data: Dict[str, Any]):
        """Send a quota update to all connected clients."""
        message = {
            "type": "quota_update",
            "quota_status": quota_data,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        await self.broadcast(json.dumps(message))
        logger.debug("Sent quota update to all clients")

    async def send_agent_status_update(self, agent_data: Dict[str, Any]):
        """Send an agent status update to all connected clients."""
        message = {
            "type": "agent_status_update",
            "agent": agent_data,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        await self.broadcast(json.dumps(message))
        logger.debug(
            f"Sent agent status update for agent {agent_data.get('id', 'unknown')}"
        )

    async def send_system_notification(self, notification: Dict[str, Any]):
        """Send a system notification to all connected clients."""
        message = {
            "type": "system_notification",
            "notification": notification,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        await self.broadcast(json.dumps(message))
        logger.info(
            f"Sent system notification: {notification.get('message', 'No message')}"
        )

    async def send_chat_update(self, chat_data: Dict[str, Any]):
        """Send a chat update to all connected clients."""
        message = {
            "type": "chat_update",
            "data": chat_data,
            "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
        }

        await self.broadcast(json.dumps(message))
        logger.debug(f"Sent chat update: {chat_data.get('type', 'unknown')}")


# Global WebSocket manager instance
websocket_manager = WebSocketManager()


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket.accept()
    websocket_manager.connect(websocket)

    try:
        # Send initial connection confirmation
        await websocket_manager.send_personal_message(
            json.dumps(
                {
                    "type": "connection_established",
                    "message": "Connected to Supervisor Coding Agent",
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                }
            ),
            websocket,
        )

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()

                # Handle client messages
                try:
                    message = json.loads(data)
                    await handle_client_message(message, websocket)
                except json.JSONDecodeError:
                    await websocket_manager.send_personal_message(
                        json.dumps(
                            {
                                "type": "error",
                                "message": "Invalid JSON format",
                                "timestamp": datetime.now(
                                    timezone.utc
                                ).isoformat()
                                + "Z",
                            }
                        ),
                        websocket,
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in WebSocket endpoint: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        websocket_manager.disconnect(websocket)


async def handle_client_message(message: Dict[str, Any], websocket: WebSocket):
    """Handle messages received from WebSocket clients."""
    message_type = message.get("type")

    if message_type == "ping":
        # Respond to ping with pong
        await websocket_manager.send_personal_message(
            json.dumps(
                {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                }
            ),
            websocket,
        )

    elif message_type == "subscribe":
        # Handle subscription to specific updates
        subscription_type = message.get("subscription_type")
        logger.info(f"Client subscribed to: {subscription_type}")

        await websocket_manager.send_personal_message(
            json.dumps(
                {
                    "type": "subscription_confirmed",
                    "subscription_type": subscription_type,
                    "timestamp": datetime.now(timezone.utc).isoformat() + "Z",
                }
            ),
            websocket,
        )

    else:
        logger.warning(f"Unknown message type: {message_type}")


# Utility functions for triggering WebSocket updates
async def notify_task_update(task_data: Dict[str, Any]):
    """Notify all WebSocket clients of a task update."""
    await websocket_manager.send_task_update(task_data)


async def notify_quota_update(quota_data: Dict[str, Any]):
    """Notify all WebSocket clients of a quota update."""
    await websocket_manager.send_quota_update(quota_data)


async def notify_agent_status_update(agent_data: Dict[str, Any]):
    """Notify all WebSocket clients of an agent status update."""
    await websocket_manager.send_agent_status_update(agent_data)


async def notify_system_event(
    event_type: str, message: str, details: Dict[str, Any] = None
):
    """Notify all WebSocket clients of a system event."""
    notification = {
        "event_type": event_type,
        "message": message,
        "details": details or {},
    }

    await websocket_manager.send_system_notification(notification)


async def notify_chat_update(chat_data: Dict[str, Any]):
    """Notify all WebSocket clients of a chat update."""
    await websocket_manager.send_chat_update(chat_data)
