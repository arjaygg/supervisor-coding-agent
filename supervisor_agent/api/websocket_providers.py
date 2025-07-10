"""
WebSocket Provider Monitoring

Real-time WebSocket feeds for multi-provider system monitoring,
health status updates, and task execution events.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from supervisor_agent.core.enhanced_agent_manager import enhanced_agent_manager
from supervisor_agent.core.multi_provider_service import multi_provider_service

logger = logging.getLogger(__name__)

router = APIRouter()


class ProviderWebSocketManager:
    """Manages WebSocket connections for provider monitoring"""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.subscription_filters: Dict[WebSocket, Dict[str, Any]] = {}
        self._monitoring_task: Optional[asyncio.Task] = None
        self._last_status: Dict[str, Any] = {}

    async def connect(
        self, websocket: WebSocket, filters: Optional[Dict[str, Any]] = None
    ):
        """Connect a new WebSocket client"""
        await websocket.accept()
        self.active_connections.add(websocket)

        if filters:
            self.subscription_filters[websocket] = filters

        logger.info(
            f"WebSocket client connected. Total connections: {len(self.active_connections)}"
        )

        # Send initial status
        try:
            await self.send_initial_status(websocket)
        except Exception as e:
            logger.error(f"Error sending initial status: {str(e)}")

        # Start monitoring if this is the first connection
        if len(self.active_connections) == 1:
            await self.start_monitoring()

    async def disconnect(self, websocket: WebSocket):
        """Disconnect a WebSocket client"""
        self.active_connections.discard(websocket)
        self.subscription_filters.pop(websocket, None)

        logger.info(
            f"WebSocket client disconnected. Total connections: {len(self.active_connections)}"
        )

        # Stop monitoring if no connections remain
        if len(self.active_connections) == 0:
            await self.stop_monitoring()

    async def start_monitoring(self):
        """Start the background monitoring task"""
        if self._monitoring_task is None or self._monitoring_task.done():
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("Started provider monitoring task")

    async def stop_monitoring(self):
        """Stop the background monitoring task"""
        if self._monitoring_task and not self._monitoring_task.done():
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
            logger.info("Stopped provider monitoring task")

    async def send_initial_status(self, websocket: WebSocket):
        """Send initial status to a newly connected client"""
        try:
            # Get comprehensive status
            provider_status = await multi_provider_service.get_provider_status()
            system_health = await enhanced_agent_manager.get_system_health()
            analytics = await multi_provider_service.get_analytics()

            initial_data = {
                "type": "initial_status",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "provider_status": provider_status,
                    "system_health": system_health,
                    "analytics": analytics,
                    "connection_id": id(websocket),
                },
            }

            await websocket.send_text(json.dumps(initial_data))

        except Exception as e:
            logger.error(f"Error sending initial status: {str(e)}")

    async def broadcast_update(self, update_type: str, data: Any):
        """Broadcast an update to all connected clients"""
        if not self.active_connections:
            return

        message = {
            "type": update_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        }

        message_text = json.dumps(message)

        # Send to all connected clients
        disconnected_clients = set()

        for websocket in self.active_connections:
            try:
                # Apply filters if any
                if self._should_send_to_client(websocket, update_type, data):
                    await websocket.send_text(message_text)

            except WebSocketDisconnect:
                disconnected_clients.add(websocket)
            except Exception as e:
                logger.error(f"Error sending message to client: {str(e)}")
                disconnected_clients.add(websocket)

        # Clean up disconnected clients
        for websocket in disconnected_clients:
            await self.disconnect(websocket)

    def _should_send_to_client(
        self, websocket: WebSocket, update_type: str, data: Any
    ) -> bool:
        """Check if update should be sent to specific client based on filters"""
        filters = self.subscription_filters.get(websocket)
        if not filters:
            return True  # No filters, send everything

        # Apply provider filter
        if "providers" in filters:
            provider_filter = filters["providers"]
            if (
                update_type == "provider_health"
                and data.get("provider_id") not in provider_filter
            ):
                return False

        # Apply update type filter
        if "update_types" in filters:
            type_filter = filters["update_types"]
            if update_type not in type_filter:
                return False

        # Apply severity filter
        if "min_severity" in filters:
            min_severity = filters["min_severity"]
            data_severity = data.get("severity", "info")

            severity_levels = {
                "debug": 0,
                "info": 1,
                "warning": 2,
                "error": 3,
                "critical": 4,
            }
            if severity_levels.get(data_severity, 1) < severity_levels.get(
                min_severity, 1
            ):
                return False

        return True

    async def _monitoring_loop(self):
        """Main monitoring loop that checks for updates"""
        try:
            while True:
                await self._check_and_broadcast_updates()
                await asyncio.sleep(5)  # Check every 5 seconds

        except asyncio.CancelledError:
            logger.info("Monitoring loop cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in monitoring loop: {str(e)}")

    async def _check_and_broadcast_updates(self):
        """Check for status changes and broadcast updates"""
        try:
            # Get current status
            current_status = await multi_provider_service.get_provider_status()

            # Compare with last status and identify changes
            if self._last_status:
                changes = self._detect_changes(self._last_status, current_status)

                for change in changes:
                    await self.broadcast_update(change["type"], change["data"])

            else:
                # First time - send full status
                await self.broadcast_update("provider_status", current_status)

            self._last_status = current_status

            # Also check system health
            system_health = await enhanced_agent_manager.get_system_health()
            await self.broadcast_update("system_health", system_health)

            # Send analytics updates every minute
            if datetime.now(timezone.utc).second < 5:  # Roughly once per minute
                analytics = await multi_provider_service.get_analytics()
                await self.broadcast_update("analytics", analytics)

        except Exception as e:
            logger.error(f"Error checking for updates: {str(e)}")

    def _detect_changes(
        self, old_status: Dict, new_status: Dict
    ) -> List[Dict[str, Any]]:
        """Detect changes between status updates"""
        changes = []

        try:
            old_providers = old_status.get("providers", {})
            new_providers = new_status.get("providers", {})

            # Check for provider health changes
            for provider_id, new_info in new_providers.items():
                old_info = old_providers.get(provider_id, {})

                # Health status change
                old_health = old_info.get("health_status")
                new_health = new_info.get("health_status")

                if old_health != new_health:
                    changes.append(
                        {
                            "type": "provider_health_change",
                            "data": {
                                "provider_id": provider_id,
                                "old_status": old_health,
                                "new_status": new_health,
                                "health_score": new_info.get("health_score", 0.0),
                                "severity": self._get_health_severity(new_health),
                            },
                        }
                    )

                # Health score significant change (>10% difference)
                old_score = old_info.get("health_score", 0.0)
                new_score = new_info.get("health_score", 0.0)

                if abs(old_score - new_score) > 0.1:
                    changes.append(
                        {
                            "type": "provider_score_change",
                            "data": {
                                "provider_id": provider_id,
                                "old_score": old_score,
                                "new_score": new_score,
                                "severity": ("warning" if new_score < 0.5 else "info"),
                            },
                        }
                    )

            # Check for new/removed providers
            old_provider_ids = set(old_providers.keys())
            new_provider_ids = set(new_providers.keys())

            # New providers
            for provider_id in new_provider_ids - old_provider_ids:
                changes.append(
                    {
                        "type": "provider_added",
                        "data": {
                            "provider_id": provider_id,
                            "provider_info": new_providers[provider_id],
                            "severity": "info",
                        },
                    }
                )

            # Removed providers
            for provider_id in old_provider_ids - new_provider_ids:
                changes.append(
                    {
                        "type": "provider_removed",
                        "data": {
                            "provider_id": provider_id,
                            "severity": "warning",
                        },
                    }
                )

            # Check quota status changes
            old_quotas = old_status.get("quota_status", {})
            new_quotas = new_status.get("quota_status", {})

            for provider_id, new_quota in new_quotas.items():
                old_quota = old_quotas.get(provider_id, {})

                old_quota_status = old_quota.get("status")
                new_quota_status = new_quota.get("status")

                if old_quota_status != new_quota_status:
                    changes.append(
                        {
                            "type": "quota_status_change",
                            "data": {
                                "provider_id": provider_id,
                                "old_status": old_quota_status,
                                "new_status": new_quota_status,
                                "usage_percentage": new_quota.get(
                                    "usage_percentage", 0
                                ),
                                "requests_remaining": new_quota.get(
                                    "requests_remaining", 0
                                ),
                                "severity": self._get_quota_severity(new_quota_status),
                            },
                        }
                    )

        except Exception as e:
            logger.error(f"Error detecting changes: {str(e)}")

        return changes

    def _get_health_severity(self, health_status: str) -> str:
        """Get severity level for health status"""
        severity_map = {
            "healthy": "info",
            "degraded": "warning",
            "unhealthy": "error",
            "error": "critical",
        }
        return severity_map.get(health_status, "info")

    def _get_quota_severity(self, quota_status: str) -> str:
        """Get severity level for quota status"""
        severity_map = {
            "available": "info",
            "warning": "warning",
            "critical": "error",
            "exhausted": "critical",
        }
        return severity_map.get(quota_status, "info")


# Global WebSocket manager
provider_ws_manager = ProviderWebSocketManager()


@router.websocket("/ws/providers")
async def websocket_provider_monitoring(websocket: WebSocket):
    """
    WebSocket endpoint for real-time provider monitoring

    Query parameters:
    - providers: Comma-separated list of provider IDs to monitor
    - update_types: Comma-separated list of update types to receive
    - min_severity: Minimum severity level (debug, info, warning, error, critical)
    """
    filters = {}

    # Parse query parameters for filtering
    query_params = websocket.query_params

    if "providers" in query_params:
        filters["providers"] = query_params["providers"].split(",")

    if "update_types" in query_params:
        filters["update_types"] = query_params["update_types"].split(",")

    if "min_severity" in query_params:
        filters["min_severity"] = query_params["min_severity"]

    try:
        await provider_ws_manager.connect(websocket, filters)

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for incoming messages (like subscription updates)
                data = await websocket.receive_text()
                message = json.loads(data)

                # Handle subscription updates
                if message.get("type") == "update_filters":
                    new_filters = message.get("filters", {})
                    provider_ws_manager.subscription_filters[websocket] = new_filters
                    logger.info(f"Updated filters for WebSocket client: {new_filters}")

                elif message.get("type") == "ping":
                    # Respond to ping
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "pong",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                        )
                    )

            except WebSocketDisconnect:
                break
            except json.JSONDecodeError:
                await websocket.send_text(
                    json.dumps({"type": "error", "message": "Invalid JSON format"})
                )
            except Exception as e:
                logger.error(f"Error handling WebSocket message: {str(e)}")

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
    finally:
        await provider_ws_manager.disconnect(websocket)


@router.websocket("/ws/provider/{provider_id}")
async def websocket_single_provider(websocket: WebSocket, provider_id: str):
    """WebSocket endpoint for monitoring a single provider"""
    filters = {"providers": [provider_id]}

    try:
        await provider_ws_manager.connect(websocket, filters)

        while True:
            try:
                # Send provider-specific updates
                data = await websocket.receive_text()
                message = json.loads(data)

                if message.get("type") == "get_status":
                    # Send current provider status
                    status = await multi_provider_service.get_provider_status()
                    provider_info = status.get("providers", {}).get(provider_id)

                    if provider_info:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "provider_status",
                                    "provider_id": provider_id,
                                    "data": provider_info,
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                        )
                    else:
                        await websocket.send_text(
                            json.dumps(
                                {
                                    "type": "error",
                                    "message": f"Provider {provider_id} not found",
                                }
                            )
                        )

            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"Error in single provider WebSocket: {str(e)}")

    except WebSocketDisconnect:
        pass
    finally:
        await provider_ws_manager.disconnect(websocket)
