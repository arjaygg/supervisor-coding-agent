"""
WebSocket endpoints for real-time analytics data streaming.
Provides live updates for dashboards and metrics.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from supervisor_agent.core.analytics_engine import AnalyticsEngine
from supervisor_agent.core.metrics_collector import MetricsCollector
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter()

# Global connection managers
analytics_connections: Set[WebSocket] = set()
analytics_engine = AnalyticsEngine()
metrics_collector = MetricsCollector()


class AnalyticsWebSocketManager:
    """Manages WebSocket connections for analytics updates"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.update_interval = 5  # seconds
        self.running = False

    async def connect(self, websocket: WebSocket):
        """Add a new WebSocket connection"""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(
            f"Analytics WebSocket connected. Total connections: {len(self.active_connections)}"
        )

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(
                f"Analytics WebSocket disconnected. Total connections: {len(self.active_connections)}"
            )

    async def broadcast_analytics_update(self, data: Dict):
        """Broadcast analytics update to all connected clients"""
        if not self.active_connections:
            return

        message = {
            "type": "analytics_update",
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.warning(f"Error sending analytics update: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def start_analytics_streaming(self):
        """Start background task for periodic analytics updates"""
        if self.running:
            return

        self.running = True
        logger.info("Starting analytics streaming background task")

        while self.running:
            try:
                await asyncio.sleep(self.update_interval)

                if self.active_connections:
                    # Get latest analytics summary
                    summary = await analytics_engine.get_summary_analytics()

                    # Create update payload
                    update_data = {
                        "summary": {
                            "total_tasks": summary.total_tasks,
                            "successful_tasks": summary.successful_tasks,
                            "failed_tasks": summary.failed_tasks,
                            "average_execution_time_ms": summary.average_execution_time_ms,
                            "system_health_score": summary.system_health_score,
                            "cost_today_usd": summary.cost_today_usd,
                        },
                        "metrics": {
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "queue_depth": summary.current_queue_depth,
                            "active_workflows": summary.active_workflows,
                        },
                    }

                    await self.broadcast_analytics_update(update_data)

            except Exception as e:
                logger.error(f"Error in analytics streaming: {e}")
                await asyncio.sleep(1)  # Brief pause before retry

    def stop_analytics_streaming(self):
        """Stop background analytics streaming"""
        self.running = False
        logger.info("Stopping analytics streaming background task")


# Global manager instance
analytics_ws_manager = AnalyticsWebSocketManager()


@router.websocket("/ws/analytics")
async def analytics_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time analytics updates"""
    await analytics_ws_manager.connect(websocket)

    try:
        # Send initial analytics data
        try:
            summary = await analytics_engine.get_summary_analytics()
            initial_data = {
                "type": "initial_analytics",
                "data": {
                    "summary": {
                        "total_tasks": summary.total_tasks,
                        "successful_tasks": summary.successful_tasks,
                        "failed_tasks": summary.failed_tasks,
                        "average_execution_time_ms": summary.average_execution_time_ms,
                        "system_health_score": summary.system_health_score,
                        "cost_today_usd": summary.cost_today_usd,
                    }
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            await websocket.send_text(json.dumps(initial_data))
        except Exception as e:
            logger.error(f"Error sending initial analytics data: {e}")

        # Start streaming if not already running
        if not analytics_ws_manager.running:
            asyncio.create_task(analytics_ws_manager.start_analytics_streaming())

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()

                # Handle client messages
                try:
                    message = json.loads(data)
                    await handle_analytics_client_message(message, websocket)
                except json.JSONDecodeError:
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "message": "Invalid JSON format",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in analytics WebSocket endpoint: {e}")
                break

    except Exception as e:
        logger.error(f"Analytics WebSocket connection error: {e}")
    finally:
        analytics_ws_manager.disconnect(websocket)


async def handle_analytics_client_message(message: Dict, websocket: WebSocket):
    """Handle messages received from analytics WebSocket clients"""
    message_type = message.get("type")

    if message_type == "ping":
        # Respond to ping with pong
        await websocket.send_text(
            json.dumps(
                {
                    "type": "pong",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        )

    elif message_type == "subscribe_metrics":
        # Handle subscription to specific metrics
        metric_types = message.get("metric_types", [])
        logger.info(f"Client subscribed to metrics: {metric_types}")

        await websocket.send_text(
            json.dumps(
                {
                    "type": "subscription_confirmed",
                    "metric_types": metric_types,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
        )

    elif message_type == "request_analytics":
        # Handle request for specific analytics data
        time_range = message.get("time_range", "day")
        try:
            # Get analytics summary
            summary = await analytics_engine.get_summary_analytics()

            response_data = {
                "type": "analytics_response",
                "data": {
                    "summary": {
                        "total_tasks": summary.total_tasks,
                        "successful_tasks": summary.successful_tasks,
                        "failed_tasks": summary.failed_tasks,
                        "average_execution_time_ms": summary.average_execution_time_ms,
                        "system_health_score": summary.system_health_score,
                        "cost_today_usd": summary.cost_today_usd,
                    },
                    "time_range": time_range,
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            await websocket.send_text(json.dumps(response_data))

        except Exception as e:
            logger.error(f"Error handling analytics request: {e}")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "error",
                        "message": f"Failed to get analytics data: {str(e)}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )

    else:
        logger.warning(f"Unknown analytics message type: {message_type}")


# Utility functions for triggering analytics updates
async def notify_analytics_update(data: Dict):
    """Notify all analytics WebSocket clients of an update"""
    await analytics_ws_manager.broadcast_analytics_update(data)


async def start_analytics_background_streaming():
    """Start the analytics background streaming task"""
    await analytics_ws_manager.start_analytics_streaming()


def stop_analytics_background_streaming():
    """Stop the analytics background streaming task"""
    analytics_ws_manager.stop_analytics_streaming()
