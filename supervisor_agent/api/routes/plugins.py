"""
Plugin Management API Routes

RESTful API endpoints for managing the plugin system, including loading,
activating, configuring, and monitoring plugins as part of Phase 1.3
Plugin Architecture implementation.

Features:
- Plugin lifecycle management (load, activate, deactivate, unload)
- Configuration management per plugin
- Health monitoring and metrics
- Event system integration
- Permission management
- Plugin discovery and information

Security:
- Role-based access control for plugin operations
- Permission validation before sensitive operations
- Audit logging for plugin management actions
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from supervisor_agent.auth.dependencies import (
    require_permissions,
)
from supervisor_agent.auth.models import User
from supervisor_agent.db.database import get_db
from supervisor_agent.plugins.plugin_interface import (
    EventType,
    PluginConfiguration,
    PluginEvent,
    PluginStatus,
    PluginType,
)
from supervisor_agent.plugins.plugin_manager import PluginManager
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/plugins")

# Global plugin manager instance (would be injected in real application)
plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get plugin manager instance"""
    global plugin_manager
    if plugin_manager is None:
        plugin_manager = PluginManager()
    return plugin_manager


# Pydantic models for API requests/responses


class PluginInfo(BaseModel):
    """Plugin information response"""

    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    status: PluginStatus
    dependencies: List[str]
    permissions: List[str]
    tags: List[str]
    load_time: Optional[str] = None
    last_activity: Optional[str] = None
    error_count: int = 0
    performance_metrics: Dict[str, Any] = Field(default_factory=dict)


class PluginConfigurationRequest(BaseModel):
    """Plugin configuration update request"""

    enabled: Optional[bool] = None
    auto_start: Optional[bool] = None
    configuration: Optional[Dict[str, Any]] = None
    permissions: Optional[List[str]] = None
    resource_limits: Optional[Dict[str, Any]] = None
    retry_policy: Optional[Dict[str, Any]] = None


class PluginEventRequest(BaseModel):
    """Plugin event publishing request"""

    event_type: EventType
    target_plugin: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class NotificationRequest(BaseModel):
    """Notification sending request"""

    plugin_name: str
    recipient: str
    subject: str
    message: str
    priority: str = "normal"
    metadata: Optional[Dict[str, Any]] = None


@router.get("/", response_model=List[PluginInfo])
async def list_plugins(
    plugin_type: Optional[PluginType] = Query(
        None, description="Filter by plugin type"
    ),
    status: Optional[PluginStatus] = Query(
        None, description="Filter by status"
    ),
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """List all plugins with optional filtering"""
    try:
        manager = get_plugin_manager()
        plugins_data = manager.list_plugins()

        plugins = []
        for plugin_name, plugin_info in plugins_data.items():
            # Apply filters
            if (
                plugin_type
                and plugin_info["metadata"]["plugin_type"] != plugin_type
            ):
                continue
            if status and plugin_info["status"] != status:
                continue

            plugins.append(
                PluginInfo(
                    name=plugin_info["metadata"]["name"],
                    version=plugin_info["metadata"]["version"],
                    description=plugin_info["metadata"]["description"],
                    author=plugin_info["metadata"].get("author", "Unknown"),
                    plugin_type=plugin_info["metadata"]["plugin_type"],
                    status=plugin_info["status"],
                    dependencies=plugin_info["metadata"]["dependencies"],
                    permissions=plugin_info["metadata"].get("permissions", []),
                    tags=plugin_info["metadata"].get("tags", []),
                    load_time=plugin_info.get("load_time"),
                    last_activity=plugin_info.get("last_activity"),
                    error_count=plugin_info.get("error_count", 0),
                    performance_metrics=plugin_info.get(
                        "performance_metrics", {}
                    ),
                )
            )

        return plugins

    except Exception as e:
        logger.error(f"Failed to list plugins: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve plugins"
        )


@router.get("/{plugin_name}", response_model=PluginInfo)
async def get_plugin_info(
    plugin_name: str,
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific plugin"""
    try:
        manager = get_plugin_manager()
        plugins_data = manager.list_plugins()

        if plugin_name not in plugins_data:
            raise HTTPException(
                status_code=404, detail=f"Plugin {plugin_name} not found"
            )

        plugin_info = plugins_data[plugin_name]

        return PluginInfo(
            name=plugin_info["metadata"]["name"],
            version=plugin_info["metadata"]["version"],
            description=plugin_info["metadata"]["description"],
            author=plugin_info["metadata"].get("author", "Unknown"),
            plugin_type=plugin_info["metadata"]["plugin_type"],
            status=plugin_info["status"],
            dependencies=plugin_info["metadata"]["dependencies"],
            permissions=plugin_info["metadata"].get("permissions", []),
            tags=plugin_info["metadata"].get("tags", []),
            load_time=plugin_info.get("load_time"),
            last_activity=plugin_info.get("last_activity"),
            error_count=plugin_info.get("error_count", 0),
            performance_metrics=plugin_info.get("performance_metrics", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get plugin info for {plugin_name}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve plugin information"
        )


@router.post("/{plugin_name}/activate")
async def activate_plugin(
    plugin_name: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permissions("plugins:manage")),
    db: Session = Depends(get_db),
):
    """Activate a loaded plugin"""
    try:
        manager = get_plugin_manager()

        # Check if plugin exists
        status = manager.get_plugin_status(plugin_name)
        if status is None:
            raise HTTPException(
                status_code=404, detail=f"Plugin {plugin_name} not found"
            )

        # Activate plugin in background
        background_tasks.add_task(manager.activate_plugin, plugin_name)

        logger.info(
            f"Plugin activation requested for {plugin_name} by {current_user.username}"
        )

        return {"message": f"Plugin {plugin_name} activation started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate plugin {plugin_name}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to activate plugin"
        )


@router.post("/{plugin_name}/deactivate")
async def deactivate_plugin(
    plugin_name: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permissions("plugins:manage")),
    db: Session = Depends(get_db),
):
    """Deactivate an active plugin"""
    try:
        manager = get_plugin_manager()

        # Check if plugin exists
        status = manager.get_plugin_status(plugin_name)
        if status is None:
            raise HTTPException(
                status_code=404, detail=f"Plugin {plugin_name} not found"
            )

        # Deactivate plugin in background
        background_tasks.add_task(manager.deactivate_plugin, plugin_name)

        logger.info(
            f"Plugin deactivation requested for {plugin_name} by {current_user.username}"
        )

        return {"message": f"Plugin {plugin_name} deactivation started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to deactivate plugin {plugin_name}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to deactivate plugin"
        )


@router.delete("/{plugin_name}")
async def unload_plugin(
    plugin_name: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_permissions("plugins:manage")),
    db: Session = Depends(get_db),
):
    """Unload a plugin completely"""
    try:
        manager = get_plugin_manager()

        # Check if plugin exists
        status = manager.get_plugin_status(plugin_name)
        if status is None:
            raise HTTPException(
                status_code=404, detail=f"Plugin {plugin_name} not found"
            )

        # Unload plugin in background
        background_tasks.add_task(manager.unload_plugin, plugin_name)

        logger.info(
            f"Plugin unload requested for {plugin_name} by {current_user.username}"
        )

        return {"message": f"Plugin {plugin_name} unload started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to unload plugin {plugin_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unload plugin")


@router.get("/{plugin_name}/health")
async def check_plugin_health(
    plugin_name: str,
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """Check health status of a specific plugin"""
    try:
        manager = get_plugin_manager()

        # Get plugin instance
        plugin = manager.get_plugin(plugin_name)
        if plugin is None:
            raise HTTPException(
                status_code=404, detail=f"Plugin {plugin_name} not found"
            )

        # Perform health check
        health_result = await plugin.health_check()

        return {
            "plugin_name": plugin_name,
            "healthy": health_result.success,
            "data": health_result.data,
            "error": health_result.error,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to check health for plugin {plugin_name}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to check plugin health"
        )


@router.get("/health/all")
async def check_all_plugins_health(
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """Check health status of all active plugins"""
    try:
        manager = get_plugin_manager()
        health_results = await manager.health_check_all()

        results = {}
        for plugin_name, health_result in health_results.items():
            results[plugin_name] = {
                "healthy": health_result.success,
                "data": health_result.data,
                "error": health_result.error,
            }

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "total_plugins": len(results),
            "healthy_plugins": sum(
                1 for r in results.values() if r["healthy"]
            ),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Failed to check all plugins health: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to check plugins health"
        )


@router.get("/{plugin_name}/configuration")
async def get_plugin_configuration(
    plugin_name: str,
    current_user: User = Depends(require_permissions("plugins:configure")),
    db: Session = Depends(get_db),
):
    """Get plugin configuration"""
    try:
        manager = get_plugin_manager()

        # Check if plugin exists
        if plugin_name not in manager.configurations:
            raise HTTPException(
                status_code=404,
                detail=f"Configuration for {plugin_name} not found",
            )

        config = manager.configurations[plugin_name]

        return {
            "plugin_name": plugin_name,
            "enabled": config.enabled,
            "auto_start": config.auto_start,
            "configuration": config.configuration,
            "permissions": config.permissions,
            "resource_limits": config.resource_limits,
            "retry_policy": config.retry_policy,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get configuration for {plugin_name}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve plugin configuration"
        )


@router.put("/{plugin_name}/configuration")
async def update_plugin_configuration(
    plugin_name: str,
    config_request: PluginConfigurationRequest,
    current_user: User = Depends(require_permissions("plugins:configure")),
    db: Session = Depends(get_db),
):
    """Update plugin configuration"""
    try:
        manager = get_plugin_manager()

        # Get existing configuration or create new one
        if plugin_name not in manager.configurations:
            manager.configurations[plugin_name] = PluginConfiguration()

        config = manager.configurations[plugin_name]

        # Update configuration fields
        if config_request.enabled is not None:
            config.enabled = config_request.enabled

        if config_request.auto_start is not None:
            config.auto_start = config_request.auto_start

        if config_request.configuration is not None:
            config.configuration.update(config_request.configuration)

        if config_request.permissions is not None:
            config.permissions = config_request.permissions

        if config_request.resource_limits is not None:
            config.resource_limits = config_request.resource_limits

        if config_request.retry_policy is not None:
            config.retry_policy = config_request.retry_policy

        # Save configurations
        manager._save_configurations()

        logger.info(
            f"Configuration updated for plugin {plugin_name} by {current_user.username}"
        )

        return {"message": f"Configuration updated for plugin {plugin_name}"}

    except Exception as e:
        logger.error(
            f"Failed to update configuration for {plugin_name}: {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to update plugin configuration"
        )


@router.post("/events/publish")
async def publish_event(
    event_request: PluginEventRequest,
    current_user: User = Depends(require_permissions("plugins:manage")),
    db: Session = Depends(get_db),
):
    """Publish an event to the plugin system"""
    try:
        manager = get_plugin_manager()

        # Create event
        event = PluginEvent(
            event_id=str(id(event_request)),
            event_type=event_request.event_type,
            source_plugin="api",
            target_plugin=event_request.target_plugin,
            data=event_request.data,
            metadata={
                **event_request.metadata,
                "published_by": current_user.username,
                "published_via": "api",
            },
        )

        # Publish event
        await manager.event_bus.publish(event)

        logger.info(
            f"Event {event_request.event_type} published by {current_user.username}"
        )

        return {
            "message": "Event published successfully",
            "event_id": event.event_id,
            "event_type": event.event_type,
        }

    except Exception as e:
        logger.error(f"Failed to publish event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to publish event")


@router.get("/events/history")
async def get_event_history(
    event_type: Optional[EventType] = Query(
        None, description="Filter by event type"
    ),
    limit: int = Query(
        100, ge=1, le=1000, description="Maximum number of events to return"
    ),
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """Get plugin event history"""
    try:
        manager = get_plugin_manager()
        events = manager.event_bus.get_event_history(event_type, limit)

        return {
            "total_events": len(events),
            "filtered_by": event_type.value if event_type else None,
            "events": [
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "source_plugin": event.source_plugin,
                    "target_plugin": event.target_plugin,
                    "timestamp": event.timestamp.isoformat(),
                    "data": event.data,
                    "metadata": event.metadata,
                }
                for event in events
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get event history: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve event history"
        )


@router.post("/notifications/send")
async def send_notification(
    notification_request: NotificationRequest,
    current_user: User = Depends(require_permissions("plugins:use")),
    db: Session = Depends(get_db),
):
    """Send notification through a notification plugin"""
    try:
        manager = get_plugin_manager()

        # Get notification plugin
        if (
            notification_request.plugin_name
            not in manager.notification_plugins
        ):
            raise HTTPException(
                status_code=404,
                detail=f"Notification plugin {notification_request.plugin_name} not found or inactive",
            )

        plugin = manager.notification_plugins[notification_request.plugin_name]

        # Send notification
        result = await plugin.send_notification(
            recipient=notification_request.recipient,
            subject=notification_request.subject,
            message=notification_request.message,
            priority=notification_request.priority,
            metadata=notification_request.metadata,
        )

        if result.success:
            logger.info(
                f"Notification sent via {notification_request.plugin_name} by {current_user.username}"
            )
            return {
                "message": "Notification sent successfully",
                "plugin": notification_request.plugin_name,
                "data": result.data,
            }
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to send notification: {result.error}",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send notification: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to send notification"
        )


@router.get("/metrics")
async def get_plugin_metrics(
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """Get comprehensive plugin system metrics"""
    try:
        manager = get_plugin_manager()
        metrics = manager.get_system_metrics()

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_metrics": metrics,
        }

    except Exception as e:
        logger.error(f"Failed to get plugin metrics: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve plugin metrics"
        )


@router.get("/types/{plugin_type}")
async def get_plugins_by_type(
    plugin_type: PluginType,
    current_user: User = Depends(require_permissions("plugins:read")),
    db: Session = Depends(get_db),
):
    """Get plugins of a specific type"""
    try:
        manager = get_plugin_manager()
        plugin_names = manager.get_plugins_by_type(plugin_type)

        plugins = []
        plugins_data = manager.list_plugins()

        for plugin_name in plugin_names:
            if plugin_name in plugins_data:
                plugin_info = plugins_data[plugin_name]
                plugins.append(
                    PluginInfo(
                        name=plugin_info["metadata"]["name"],
                        version=plugin_info["metadata"]["version"],
                        description=plugin_info["metadata"]["description"],
                        author=plugin_info["metadata"].get(
                            "author", "Unknown"
                        ),
                        plugin_type=plugin_info["metadata"]["plugin_type"],
                        status=plugin_info["status"],
                        dependencies=plugin_info["metadata"]["dependencies"],
                        permissions=plugin_info["metadata"].get(
                            "permissions", []
                        ),
                        tags=plugin_info["metadata"].get("tags", []),
                        load_time=plugin_info.get("load_time"),
                        last_activity=plugin_info.get("last_activity"),
                        error_count=plugin_info.get("error_count", 0),
                        performance_metrics=plugin_info.get(
                            "performance_metrics", {}
                        ),
                    )
                )

        return {
            "plugin_type": plugin_type,
            "total_plugins": len(plugins),
            "plugins": plugins,
        }

    except Exception as e:
        logger.error(f"Failed to get plugins by type {plugin_type}: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to retrieve plugins by type"
        )


@router.post("/discover")
async def discover_plugins(
    current_user: User = Depends(require_permissions("plugins:manage")),
    db: Session = Depends(get_db),
):
    """Discover available plugins in configured directories"""
    try:
        manager = get_plugin_manager()
        discovered = await manager.discover_plugins()

        return {
            "message": "Plugin discovery completed",
            "discovered_plugins": len(discovered),
            "plugins": discovered,
        }

    except Exception as e:
        logger.error(f"Failed to discover plugins: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Failed to discover plugins"
        )
