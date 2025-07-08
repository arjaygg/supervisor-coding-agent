"""
Real-time Monitoring API Routes

Provides comprehensive real-time monitoring capabilities including:
- Live system metrics streaming
- Performance alerts and notifications
- Health check endpoints
- Capacity planning insights
- Automated monitoring configuration
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from supervisor_agent.core.resource_allocation_engine import DynamicResourceAllocator
from supervisor_agent.db.database import get_db
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/monitoring", tags=["real-time-monitoring"])

# Global instances
resource_allocator = DynamicResourceAllocator()


class MonitoringConfig(BaseModel):
    """Monitoring configuration"""
    enabled: bool = Field(True, description="Enable/disable monitoring")
    sampling_interval: int = Field(30, description="Sampling interval in seconds")
    alert_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "cpu_critical": 90.0,
            "cpu_warning": 80.0,
            "memory_critical": 90.0,
            "memory_warning": 80.0,
            "disk_critical": 95.0,
            "disk_warning": 85.0,
        }
    )
    retention_hours: int = Field(24, description="Data retention in hours")


class AlertRule(BaseModel):
    """Alert rule configuration"""
    name: str = Field(..., description="Rule name")
    metric: str = Field(..., description="Metric to monitor")
    condition: str = Field(..., description="Alert condition (gt, lt, eq)")
    threshold: float = Field(..., description="Alert threshold")
    severity: str = Field(..., description="Alert severity (info, warning, critical)")
    enabled: bool = Field(True, description="Rule enabled status")


class SystemAlert(BaseModel):
    """System alert model"""
    id: str
    rule_name: str
    metric: str
    current_value: float
    threshold: float
    severity: str
    message: str
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    status: str  # active, resolved, suppressed


# WebSocket connection manager for real-time monitoring
class MonitoringWebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.monitoring_config = MonitoringConfig()
        self.active_alerts: Dict[str, SystemAlert] = {}
        self.alert_rules: Dict[str, AlertRule] = self._default_alert_rules()

    def _default_alert_rules(self) -> Dict[str, AlertRule]:
        """Default alert rules"""
        return {
            "cpu_critical": AlertRule(
                name="CPU Critical",
                metric="cpu_percent",
                condition="gt",
                threshold=90.0,
                severity="critical"
            ),
            "cpu_warning": AlertRule(
                name="CPU Warning",
                metric="cpu_percent",
                condition="gt",
                threshold=80.0,
                severity="warning"
            ),
            "memory_critical": AlertRule(
                name="Memory Critical",
                metric="memory_percent",
                condition="gt",
                threshold=90.0,
                severity="critical"
            ),
            "memory_warning": AlertRule(
                name="Memory Warning",
                metric="memory_percent",
                condition="gt",
                threshold=80.0,
                severity="warning"
            )
        }

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"Monitoring WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"Monitoring WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Failed to send WebSocket message: {str(e)}")
                disconnected.append(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def start_monitoring(self):
        """Start the monitoring loop"""
        while True:
            if self.monitoring_config.enabled and self.active_connections:
                try:
                    # Collect metrics
                    metrics = await resource_allocator.monitor_resource_usage()
                    
                    # Check alert rules
                    alerts = await self._check_alert_rules(metrics)
                    
                    # Prepare monitoring data
                    monitoring_data = {
                        "type": "monitoring_update",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "metrics": {
                            "cpu_percent": metrics.cpu_percent,
                            "memory_percent": metrics.memory_percent,
                            "disk_percent": metrics.disk_percent,
                            "network_io": metrics.network_io,
                        },
                        "alerts": [
                            {
                                "id": alert.id,
                                "rule_name": alert.rule_name,
                                "severity": alert.severity,
                                "message": alert.message,
                                "current_value": alert.current_value,
                                "threshold": alert.threshold,
                                "status": alert.status,
                                "triggered_at": alert.triggered_at.isoformat()
                            }
                            for alert in alerts
                        ],
                        "system_health": self._calculate_system_health(metrics),
                        "active_alert_count": len([a for a in self.active_alerts.values() if a.status == "active"])
                    }

                    # Broadcast to all connected clients
                    await self.broadcast(monitoring_data)

                except Exception as e:
                    logger.error(f"Monitoring loop error: {str(e)}")

            # Wait for next sampling interval
            await asyncio.sleep(self.monitoring_config.sampling_interval)

    async def _check_alert_rules(self, metrics) -> List[SystemAlert]:
        """Check all alert rules against current metrics"""
        current_alerts = []
        
        for rule_name, rule in self.alert_rules.items():
            if not rule.enabled:
                continue

            # Get metric value
            metric_value = getattr(metrics, rule.metric, None)
            if metric_value is None:
                continue

            # Check condition
            alert_triggered = False
            if rule.condition == "gt" and metric_value > rule.threshold:
                alert_triggered = True
            elif rule.condition == "lt" and metric_value < rule.threshold:
                alert_triggered = True
            elif rule.condition == "eq" and metric_value == rule.threshold:
                alert_triggered = True

            alert_id = f"{rule_name}_{rule.metric}"
            
            if alert_triggered:
                # Create or update alert
                if alert_id not in self.active_alerts:
                    alert = SystemAlert(
                        id=alert_id,
                        rule_name=rule.name,
                        metric=rule.metric,
                        current_value=metric_value,
                        threshold=rule.threshold,
                        severity=rule.severity,
                        message=f"{rule.name}: {rule.metric} is {metric_value:.1f} (threshold: {rule.threshold})",
                        triggered_at=datetime.now(timezone.utc),
                        status="active"
                    )
                    self.active_alerts[alert_id] = alert
                    logger.warning(f"Alert triggered: {alert.message}")
                else:
                    # Update existing alert
                    self.active_alerts[alert_id].current_value = metric_value
                    self.active_alerts[alert_id].message = f"{rule.name}: {rule.metric} is {metric_value:.1f} (threshold: {rule.threshold})"

                current_alerts.append(self.active_alerts[alert_id])
            else:
                # Resolve alert if it exists
                if alert_id in self.active_alerts and self.active_alerts[alert_id].status == "active":
                    self.active_alerts[alert_id].status = "resolved"
                    self.active_alerts[alert_id].resolved_at = datetime.now(timezone.utc)
                    logger.info(f"Alert resolved: {rule.name}")

        return current_alerts

    def _calculate_system_health(self, metrics) -> str:
        """Calculate overall system health score"""
        critical_issues = 0
        warning_issues = 0

        if metrics.cpu_percent > 90:
            critical_issues += 1
        elif metrics.cpu_percent > 80:
            warning_issues += 1

        if metrics.memory_percent > 90:
            critical_issues += 1
        elif metrics.memory_percent > 80:
            warning_issues += 1

        if metrics.disk_percent > 95:
            critical_issues += 1
        elif metrics.disk_percent > 85:
            warning_issues += 1

        if critical_issues > 0:
            return "critical"
        elif warning_issues > 1:
            return "degraded"
        elif warning_issues > 0:
            return "warning"
        else:
            return "healthy"


# Global monitoring manager
monitoring_manager = MonitoringWebSocketManager()


@router.websocket("/stream")
async def monitoring_websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time monitoring data"""
    await monitoring_manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and handle client messages
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=1.0)
                message = json.loads(data)
                
                # Handle client configuration updates
                if message.get("type") == "update_config":
                    config_data = message.get("config", {})
                    # Update monitoring configuration
                    if "sampling_interval" in config_data:
                        monitoring_manager.monitoring_config.sampling_interval = config_data["sampling_interval"]
                    logger.info(f"Updated monitoring config: {config_data}")
                    
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue
            except json.JSONDecodeError:
                logger.warning("Invalid JSON received from monitoring WebSocket")
            
            await asyncio.sleep(0.1)
            
    except WebSocketDisconnect:
        monitoring_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Monitoring WebSocket error: {str(e)}")
        monitoring_manager.disconnect(websocket)


@router.get("/health")
async def get_system_health():
    """Get comprehensive system health status"""
    try:
        metrics = await resource_allocator.monitor_resource_usage()
        
        health_status = monitoring_manager._calculate_system_health(metrics)
        
        # Get active alerts
        active_alerts = [
            alert for alert in monitoring_manager.active_alerts.values()
            if alert.status == "active"
        ]
        
        # Get resource utilization report
        utilization_report = await resource_allocator.get_resource_utilization_report()
        
        return {
            "status": health_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "cpu_percent": metrics.cpu_percent,
                "memory_percent": metrics.memory_percent,
                "disk_percent": metrics.disk_percent,
                "network_io": metrics.network_io,
            },
            "alerts": {
                "active_count": len(active_alerts),
                "critical_count": len([a for a in active_alerts if a.severity == "critical"]),
                "warning_count": len([a for a in active_alerts if a.severity == "warning"]),
                "recent_alerts": [
                    {
                        "rule_name": alert.rule_name,
                        "severity": alert.severity,
                        "message": alert.message,
                        "triggered_at": alert.triggered_at.isoformat()
                    }
                    for alert in sorted(active_alerts, key=lambda x: x.triggered_at, reverse=True)[:5]
                ]
            },
            "utilization": utilization_report,
            "monitoring": {
                "enabled": monitoring_manager.monitoring_config.enabled,
                "sampling_interval": monitoring_manager.monitoring_config.sampling_interval,
                "connected_clients": len(monitoring_manager.active_connections),
                "alert_rules_count": len(monitoring_manager.alert_rules)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get system health: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    status: Optional[str] = Query(None, description="Filter by status: active, resolved, all"),
    severity: Optional[str] = Query(None, description="Filter by severity: info, warning, critical"),
    limit: int = Query(50, description="Maximum number of alerts to return")
):
    """Get system alerts with filtering"""
    try:
        alerts = list(monitoring_manager.active_alerts.values())
        
        # Apply filters
        if status and status != "all":
            alerts = [alert for alert in alerts if alert.status == status]
        
        if severity:
            alerts = [alert for alert in alerts if alert.severity == severity]
        
        # Sort by triggered time (most recent first)
        alerts.sort(key=lambda x: x.triggered_at, reverse=True)
        
        # Apply limit
        alerts = alerts[:limit]
        
        return {
            "total_alerts": len(alerts),
            "filters": {
                "status": status,
                "severity": severity,
                "limit": limit
            },
            "alerts": [
                {
                    "id": alert.id,
                    "rule_name": alert.rule_name,
                    "metric": alert.metric,
                    "current_value": alert.current_value,
                    "threshold": alert.threshold,
                    "severity": alert.severity,
                    "message": alert.message,
                    "triggered_at": alert.triggered_at.isoformat(),
                    "resolved_at": alert.resolved_at.isoformat() if alert.resolved_at else None,
                    "status": alert.status
                }
                for alert in alerts
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/rules")
async def create_alert_rule(rule: AlertRule):
    """Create a new alert rule"""
    try:
        rule_id = f"{rule.name.lower().replace(' ', '_')}_{rule.metric}"
        
        if rule_id in monitoring_manager.alert_rules:
            raise HTTPException(status_code=400, detail="Alert rule already exists")
        
        monitoring_manager.alert_rules[rule_id] = rule
        
        logger.info(f"Created alert rule: {rule.name}")
        
        return {
            "rule_id": rule_id,
            "message": "Alert rule created successfully",
            "rule": {
                "name": rule.name,
                "metric": rule.metric,
                "condition": rule.condition,
                "threshold": rule.threshold,
                "severity": rule.severity,
                "enabled": rule.enabled
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create alert rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/rules")
async def get_alert_rules():
    """Get all alert rules"""
    try:
        return {
            "total_rules": len(monitoring_manager.alert_rules),
            "rules": [
                {
                    "rule_id": rule_id,
                    "name": rule.name,
                    "metric": rule.metric,
                    "condition": rule.condition,
                    "threshold": rule.threshold,
                    "severity": rule.severity,
                    "enabled": rule.enabled
                }
                for rule_id, rule in monitoring_manager.alert_rules.items()
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get alert rules: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/alerts/rules/{rule_id}")
async def delete_alert_rule(rule_id: str):
    """Delete an alert rule"""
    try:
        if rule_id not in monitoring_manager.alert_rules:
            raise HTTPException(status_code=404, detail="Alert rule not found")
        
        rule = monitoring_manager.alert_rules.pop(rule_id)
        
        # Resolve any active alerts for this rule
        for alert_id, alert in monitoring_manager.active_alerts.items():
            if alert.rule_name == rule.name and alert.status == "active":
                alert.status = "resolved"
                alert.resolved_at = datetime.now(timezone.utc)
        
        logger.info(f"Deleted alert rule: {rule.name}")
        
        return {"message": "Alert rule deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete alert rule: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_monitoring_config():
    """Get current monitoring configuration"""
    return {
        "config": {
            "enabled": monitoring_manager.monitoring_config.enabled,
            "sampling_interval": monitoring_manager.monitoring_config.sampling_interval,
            "alert_thresholds": monitoring_manager.monitoring_config.alert_thresholds,
            "retention_hours": monitoring_manager.monitoring_config.retention_hours
        },
        "status": {
            "connected_clients": len(monitoring_manager.active_connections),
            "active_alerts": len([a for a in monitoring_manager.active_alerts.values() if a.status == "active"]),
            "total_alert_rules": len(monitoring_manager.alert_rules)
        }
    }


@router.put("/config")
async def update_monitoring_config(config: MonitoringConfig):
    """Update monitoring configuration"""
    try:
        monitoring_manager.monitoring_config = config
        
        logger.info(f"Updated monitoring configuration: enabled={config.enabled}, interval={config.sampling_interval}s")
        
        return {
            "message": "Monitoring configuration updated successfully",
            "config": {
                "enabled": config.enabled,
                "sampling_interval": config.sampling_interval,
                "alert_thresholds": config.alert_thresholds,
                "retention_hours": config.retention_hours
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to update monitoring config: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/start")
async def start_monitoring(background_tasks: BackgroundTasks):
    """Start the monitoring system"""
    try:
        if not monitoring_manager.monitoring_config.enabled:
            monitoring_manager.monitoring_config.enabled = True
            
            # Start monitoring loop in background
            background_tasks.add_task(monitoring_manager.start_monitoring)
            
            logger.info("Monitoring system started")
            
            return {"message": "Monitoring system started successfully"}
        else:
            return {"message": "Monitoring system is already running"}
            
    except Exception as e:
        logger.error(f"Failed to start monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop")
async def stop_monitoring():
    """Stop the monitoring system"""
    try:
        monitoring_manager.monitoring_config.enabled = False
        
        logger.info("Monitoring system stopped")
        
        return {"message": "Monitoring system stopped successfully"}
        
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Auto-start monitoring when module loads
@router.on_event("startup")
async def startup_monitoring():
    """Auto-start monitoring on API startup"""
    try:
        import asyncio
        
        # Start monitoring loop
        asyncio.create_task(monitoring_manager.start_monitoring())
        logger.info("Real-time monitoring system auto-started")
    except Exception as e:
        logger.error(f"Failed to auto-start monitoring: {str(e)}")