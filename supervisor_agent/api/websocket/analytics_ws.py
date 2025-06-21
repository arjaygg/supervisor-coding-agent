"""
WebSocket endpoints for real-time analytics data streaming.
Provides live updates for dashboards and metrics.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Dict, Set, List, Optional
from fastapi import WebSocket, WebSocketDisconnect, Depends
from fastapi.routing import APIRouter
from sqlalchemy.orm import Session

from supervisor_agent.db.database import get_db
from supervisor_agent.core.analytics_models import MetricType, TimeRange, AnalyticsQuery, AggregationType
from supervisor_agent.core.analytics_engine import AnalyticsEngine
from supervisor_agent.core.metrics_collector import MetricsCollector, BackgroundMetricsCollector


router = APIRouter()

# Connection management
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Set[str]] = {}  # websocket_id -> set of subscription types
        
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.subscriptions[client_id] = set()
        
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.subscriptions:
            del self.subscriptions[client_id]
            
    async def send_personal_message(self, message: dict, client_id: str):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_text(json.dumps(message))
            except:
                # Connection is broken, remove it
                self.disconnect(client_id)
                
    async def broadcast_to_subscribers(self, message: dict, subscription_type: str):
        """Send message to all clients subscribed to a specific type"""
        disconnected_clients = []
        
        for client_id, subscriptions in self.subscriptions.items():
            if subscription_type in subscriptions:
                try:
                    await self.active_connections[client_id].send_text(json.dumps(message))
                except:
                    disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            self.disconnect(client_id)

manager = ConnectionManager()

# Initialize services
analytics_engine = AnalyticsEngine()
metrics_collector = MetricsCollector()


@router.websocket("/ws/analytics/metrics/{client_id}")
async def websocket_analytics_endpoint(websocket: WebSocket, client_id: str):
    """Main WebSocket endpoint for real-time analytics"""
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive subscription requests from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            await handle_websocket_message(client_id, message)
            
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"WebSocket error for client {client_id}: {e}")
        manager.disconnect(client_id)


async def handle_websocket_message(client_id: str, message: dict):
    """Handle incoming WebSocket messages"""
    message_type = message.get("type")
    
    if message_type == "subscribe":
        # Add subscription
        subscription_type = message.get("subscription")
        if subscription_type:
            manager.subscriptions[client_id].add(subscription_type)
            
            # Send initial data for this subscription
            await send_initial_data(client_id, subscription_type)
            
            await manager.send_personal_message({
                "type": "subscription_confirmed",
                "subscription": subscription_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, client_id)
    
    elif message_type == "unsubscribe":
        # Remove subscription
        subscription_type = message.get("subscription")
        if subscription_type and client_id in manager.subscriptions:
            manager.subscriptions[client_id].discard(subscription_type)
            
            await manager.send_personal_message({
                "type": "subscription_removed",
                "subscription": subscription_type,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, client_id)
    
    elif message_type == "query":
        # Execute custom analytics query
        try:
            query_data = message.get("query")
            if query_data:
                query = AnalyticsQuery(**query_data)
                result = await analytics_engine.process_metrics(query)
                
                await manager.send_personal_message({
                    "type": "query_result",
                    "query_id": message.get("query_id"),
                    "result": {
                        "data": [
                            {
                                "timestamp": point.timestamp.isoformat(),
                                "value": point.value,
                                "labels": point.labels,
                                "metadata": point.metadata
                            }
                            for point in result.data
                        ],
                        "total_points": result.total_points,
                        "processing_time_ms": result.processing_time_ms,
                        "cache_hit": result.cache_hit
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }, client_id)
        except Exception as e:
            await manager.send_personal_message({
                "type": "error",
                "message": f"Query execution failed: {str(e)}",
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, client_id)


async def send_initial_data(client_id: str, subscription_type: str):
    """Send initial data when client subscribes"""
    try:
        if subscription_type == "system_metrics":
            # Send current system metrics
            summary = await analytics_engine.get_summary_analytics()
            await manager.send_personal_message({
                "type": "system_metrics",
                "data": {
                    "total_tasks": summary.total_tasks,
                    "successful_tasks": summary.successful_tasks,
                    "failed_tasks": summary.failed_tasks,
                    "average_execution_time_ms": summary.average_execution_time_ms,
                    "current_queue_depth": summary.current_queue_depth,
                    "system_health_score": summary.system_health_score,
                    "active_workflows": summary.active_workflows,
                    "cost_today_usd": summary.cost_today_usd
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, client_id)
        
        elif subscription_type == "insights":
            # Send current insights
            insights = await analytics_engine.generate_insights(TimeRange.DAY)
            await manager.send_personal_message({
                "type": "insights",
                "data": [
                    {
                        "title": insight.title,
                        "description": insight.description,
                        "severity": insight.severity,
                        "metric_type": insight.metric_type.value,
                        "value": insight.value,
                        "threshold": insight.threshold,
                        "recommendation": insight.recommendation,
                        "created_at": insight.created_at.isoformat()
                    }
                    for insight in insights
                ],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, client_id)
        
        elif subscription_type == "task_metrics":
            # Send recent task metrics
            query = AnalyticsQuery(
                metric_type=MetricType.TASK_EXECUTION,
                time_range=TimeRange.HOUR,
                aggregation=AggregationType.COUNT,
                group_by=["time"]
            )
            result = await analytics_engine.process_metrics(query)
            
            await manager.send_personal_message({
                "type": "task_metrics",
                "data": [
                    {
                        "timestamp": point.timestamp.isoformat(),
                        "value": point.value,
                        "labels": point.labels,
                        "metadata": point.metadata
                    }
                    for point in result.data
                ],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }, client_id)
            
    except Exception as e:
        await manager.send_personal_message({
            "type": "error",
            "message": f"Failed to send initial data: {str(e)}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }, client_id)


class AnalyticsWebSocketService:
    """Service for managing WebSocket broadcasts"""
    
    def __init__(self, connection_manager: ConnectionManager):
        self.manager = connection_manager
        self._running = False
        self._broadcast_task = None
        
    async def start_broadcasting(self):
        """Start periodic broadcasts to subscribers"""
        if self._running:
            return
            
        self._running = True
        self._broadcast_task = asyncio.create_task(self._broadcast_loop())
    
    async def stop_broadcasting(self):
        """Stop periodic broadcasts"""
        self._running = False
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
    
    async def _broadcast_loop(self):
        """Main broadcast loop"""
        while self._running:
            try:
                # Broadcast system metrics every 30 seconds
                await self._broadcast_system_metrics()
                await asyncio.sleep(30)
                
                # Broadcast insights every 5 minutes (simplified to 60 seconds for demo)
                await self._broadcast_insights()
                await asyncio.sleep(60)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in WebSocket broadcast loop: {e}")
                await asyncio.sleep(30)
    
    async def _broadcast_system_metrics(self):
        """Broadcast system metrics to all subscribers"""
        try:
            summary = await analytics_engine.get_summary_analytics()
            
            message = {
                "type": "system_metrics_update",
                "data": {
                    "total_tasks": summary.total_tasks,
                    "successful_tasks": summary.successful_tasks,
                    "failed_tasks": summary.failed_tasks,
                    "average_execution_time_ms": summary.average_execution_time_ms,
                    "current_queue_depth": summary.current_queue_depth,
                    "system_health_score": summary.system_health_score,
                    "active_workflows": summary.active_workflows,
                    "cost_today_usd": summary.cost_today_usd
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.manager.broadcast_to_subscribers(message, "system_metrics")
            
        except Exception as e:
            print(f"Error broadcasting system metrics: {e}")
    
    async def _broadcast_insights(self):
        """Broadcast insights to all subscribers"""
        try:
            insights = await analytics_engine.generate_insights(TimeRange.DAY)
            
            message = {
                "type": "insights_update",
                "data": [
                    {
                        "title": insight.title,
                        "description": insight.description,
                        "severity": insight.severity,
                        "metric_type": insight.metric_type.value,
                        "value": insight.value,
                        "threshold": insight.threshold,
                        "recommendation": insight.recommendation,
                        "created_at": insight.created_at.isoformat()
                    }
                    for insight in insights
                ],
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.manager.broadcast_to_subscribers(message, "insights")
            
        except Exception as e:
            print(f"Error broadcasting insights: {e}")
    
    async def broadcast_task_completion(self, task_id: int, success: bool, execution_time_ms: int):
        """Broadcast when a task completes"""
        try:
            message = {
                "type": "task_completed",
                "data": {
                    "task_id": task_id,
                    "success": success,
                    "execution_time_ms": execution_time_ms,
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.manager.broadcast_to_subscribers(message, "task_metrics")
            
        except Exception as e:
            print(f"Error broadcasting task completion: {e}")
    
    async def broadcast_alert(self, alert_type: str, message: str, severity: str = "warning"):
        """Broadcast alerts to subscribers"""
        try:
            alert_message = {
                "type": "alert",
                "data": {
                    "alert_type": alert_type,
                    "message": message,
                    "severity": severity
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            await self.manager.broadcast_to_subscribers(alert_message, "alerts")
            
        except Exception as e:
            print(f"Error broadcasting alert: {e}")


# Global WebSocket service instance
websocket_service = AnalyticsWebSocketService(manager)


@router.on_event("startup")
async def startup_websocket_service():
    """Start WebSocket broadcasting service"""
    await websocket_service.start_broadcasting()


@router.on_event("shutdown")
async def shutdown_websocket_service():
    """Stop WebSocket broadcasting service"""
    await websocket_service.stop_broadcasting()