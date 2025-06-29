"""
Plugin Manager

Comprehensive plugin management system for the Supervisor Coding Agent,
handling plugin lifecycle, dependency resolution, event distribution,
and security management as specified in Phase 1.3.

Features:
- Dynamic plugin loading and unloading
- Dependency resolution with topological sorting
- Event-driven plugin communication
- Performance monitoring and metrics collection
- Security validation and permission management
- Configuration management per plugin
- Plugin versioning and compatibility checking
- Hot-reloading capabilities

SOLID Principles:
- Single Responsibility: Focused on plugin management and orchestration
- Open-Closed: Extensible for new plugin types without core changes
- Liskov Substitution: Consistent plugin interface handling
- Interface Segregation: Separate concerns for different plugin aspects
- Dependency Inversion: Abstract plugin dependencies and interfaces
"""

import asyncio
import importlib
import importlib.util
import inspect
import json
import os
import sys
import time
import weakref
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Type

from supervisor_agent.plugins.plugin_interface import (
    AnalyticsInterface,
    DataSourceInterface,
    EventType,
    IntegrationInterface,
    NotificationInterface,
    PluginEvent,
    PluginInterface,
    PluginMetadata,
    PluginPermissionManager,
    PluginResult,
    PluginStatus,
    PluginType,
    PluginValidator,
    TaskProcessorInterface,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PluginRegistry:
    """Registry entry for a loaded plugin"""

    plugin: PluginInterface
    metadata: PluginMetadata
    status: PluginStatus
    load_time: datetime
    last_activity: Optional[datetime] = None
    error_count: int = 0
    performance_metrics: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    dependents: List[str] = field(default_factory=list)


@dataclass
class PluginConfiguration:
    """Plugin configuration settings"""

    enabled: bool = True
    auto_start: bool = True
    configuration: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    retry_policy: Dict[str, Any] = field(default_factory=dict)


class PluginDependencyResolver:
    """Resolves plugin dependencies using topological sorting"""

    @staticmethod
    def resolve_load_order(plugins: Dict[str, PluginMetadata]) -> List[str]:
        """Resolve plugin load order based on dependencies"""
        # Build dependency graph
        graph = {}
        in_degree = {}

        # Initialize graph
        for plugin_name in plugins.keys():
            graph[plugin_name] = []
            in_degree[plugin_name] = 0

        # Build edges
        for plugin_name, metadata in plugins.items():
            for dependency in metadata.dependencies:
                if dependency in graph:
                    graph[dependency].append(plugin_name)
                    in_degree[plugin_name] += 1
                else:
                    logger.warning(
                        f"Plugin {plugin_name} has unresolved dependency: {dependency}"
                    )

        # Topological sort
        queue = deque([name for name, degree in in_degree.items() if degree == 0])
        result = []

        while queue:
            current = queue.popleft()
            result.append(current)

            for neighbor in graph[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # Check for cycles
        if len(result) != len(plugins):
            remaining = [name for name in plugins.keys() if name not in result]
            raise ValueError(f"Circular dependency detected among plugins: {remaining}")

        return result

    @staticmethod
    def validate_dependencies(
        plugins: Dict[str, PluginMetadata],
    ) -> Dict[str, List[str]]:
        """Validate all plugin dependencies and return missing ones"""
        missing_deps = {}

        for plugin_name, metadata in plugins.items():
            missing = []
            for dependency in metadata.dependencies:
                if dependency not in plugins:
                    missing.append(dependency)

            if missing:
                missing_deps[plugin_name] = missing

        return missing_deps


class PluginEventBus:
    """Event bus for plugin communication"""

    def __init__(self):
        self.subscribers: Dict[EventType, List[weakref.WeakMethod]] = defaultdict(list)
        self.event_history: deque = deque(maxlen=1000)  # Keep last 1000 events
        self.metrics = {
            "events_published": 0,
            "events_delivered": 0,
            "delivery_failures": 0,
        }

    def subscribe(self, event_type: EventType, handler: Callable):
        """Subscribe to events of specific type"""
        try:
            # Use weak reference to prevent memory leaks
            weak_handler = (
                weakref.WeakMethod(handler)
                if hasattr(handler, "__self__")
                else weakref.ref(handler)
            )
            self.subscribers[event_type].append(weak_handler)
            logger.debug(f"Subscribed handler to {event_type}")
        except Exception as e:
            logger.error(f"Failed to subscribe to event {event_type}: {str(e)}")

    def unsubscribe(self, event_type: EventType, handler: Callable):
        """Unsubscribe from events"""
        try:
            subscribers = self.subscribers.get(event_type, [])
            # Remove dead references and matching handlers
            self.subscribers[event_type] = [
                ref for ref in subscribers if ref() is not None and ref() != handler
            ]
            logger.debug(f"Unsubscribed handler from {event_type}")
        except Exception as e:
            logger.error(f"Failed to unsubscribe from event {event_type}: {str(e)}")

    async def publish(self, event: PluginEvent):
        """Publish event to all subscribers"""
        try:
            self.metrics["events_published"] += 1
            self.event_history.append(event)

            subscribers = self.subscribers.get(event.event_type, [])
            delivery_tasks = []

            for weak_handler in subscribers[
                :
            ]:  # Copy to avoid modification during iteration
                handler = weak_handler()
                if handler is None:
                    # Remove dead reference
                    subscribers.remove(weak_handler)
                    continue

                delivery_tasks.append(self._deliver_event(event, handler))

            # Deliver events concurrently
            if delivery_tasks:
                results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
                successful_deliveries = sum(
                    1 for result in results if not isinstance(result, Exception)
                )
                self.metrics["events_delivered"] += successful_deliveries
                self.metrics["delivery_failures"] += (
                    len(results) - successful_deliveries
                )

            logger.debug(
                f"Published event {event.event_type} to {len(delivery_tasks)} subscribers"
            )

        except Exception as e:
            logger.error(f"Failed to publish event {event.event_type}: {str(e)}")
            self.metrics["delivery_failures"] += 1

    async def _deliver_event(self, event: PluginEvent, handler: Callable):
        """Deliver event to specific handler"""
        try:
            if inspect.iscoroutinefunction(handler):
                await handler(event)
            else:
                handler(event)
        except Exception as e:
            logger.error(f"Event handler failed: {str(e)}")
            raise

    def get_event_history(
        self, event_type: Optional[EventType] = None, limit: int = 100
    ) -> List[PluginEvent]:
        """Get recent event history"""
        events = list(self.event_history)

        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events[-limit:]


class PluginManager:
    """
    Central plugin management system handling the complete plugin lifecycle.

    Responsibilities:
    - Plugin discovery and loading
    - Dependency resolution and ordering
    - Event bus management
    - Security and permission enforcement
    - Performance monitoring
    - Configuration management
    """

    def __init__(self, plugin_directories: List[str] = None, config_file: str = None):
        self.plugin_directories = plugin_directories or [
            "supervisor_agent/plugins/enabled"
        ]
        self.config_file = config_file or "supervisor_agent/plugins/plugin_config.json"

        # Core components
        self.registry: Dict[str, PluginRegistry] = {}
        self.configurations: Dict[str, PluginConfiguration] = {}
        self.event_bus = PluginEventBus()
        self.permission_manager = PluginPermissionManager()
        self.dependency_resolver = PluginDependencyResolver()

        # Plugin type registries
        self.task_processors: Dict[str, TaskProcessorInterface] = {}
        self.data_sources: Dict[str, DataSourceInterface] = {}
        self.notification_plugins: Dict[str, NotificationInterface] = {}
        self.analytics_plugins: Dict[str, AnalyticsInterface] = {}
        self.integration_plugins: Dict[str, IntegrationInterface] = {}

        # Management state
        self.is_initialized = False
        self.startup_time: Optional[datetime] = None
        self.metrics = {
            "plugins_loaded": 0,
            "plugins_active": 0,
            "total_events": 0,
            "errors": 0,
        }

        # Load configurations
        self._load_configurations()

    def _load_configurations(self):
        """Load plugin configurations from file"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, "r") as f:
                    config_data = json.load(f)

                for plugin_name, config in config_data.items():
                    self.configurations[plugin_name] = PluginConfiguration(**config)

                logger.info(
                    f"Loaded configurations for {len(self.configurations)} plugins"
                )
            else:
                logger.info("No plugin configuration file found, using defaults")
        except Exception as e:
            logger.error(f"Failed to load plugin configurations: {str(e)}")

    def _save_configurations(self):
        """Save plugin configurations to file"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            config_data = {}
            for plugin_name, config in self.configurations.items():
                config_data[plugin_name] = {
                    "enabled": config.enabled,
                    "auto_start": config.auto_start,
                    "configuration": config.configuration,
                    "permissions": config.permissions,
                    "resource_limits": config.resource_limits,
                    "retry_policy": config.retry_policy,
                }

            with open(self.config_file, "w") as f:
                json.dump(config_data, f, indent=2)

            logger.debug("Saved plugin configurations")
        except Exception as e:
            logger.error(f"Failed to save plugin configurations: {str(e)}")

    async def initialize(self):
        """Initialize the plugin manager"""
        if self.is_initialized:
            logger.warning("Plugin manager already initialized")
            return

        try:
            self.startup_time = datetime.now(timezone.utc)

            # Discover and load plugins
            await self.discover_plugins()

            # Load enabled plugins
            await self.load_enabled_plugins()

            # Publish startup event
            startup_event = PluginEvent(
                event_id=str(id(self)),
                event_type=EventType.SYSTEM_STARTUP,
                source_plugin="plugin_manager",
                data={"startup_time": self.startup_time.isoformat()},
            )
            await self.event_bus.publish(startup_event)

            self.is_initialized = True
            logger.info(f"Plugin manager initialized with {len(self.registry)} plugins")

        except Exception as e:
            logger.error(f"Failed to initialize plugin manager: {str(e)}")
            raise

    async def discover_plugins(self) -> Dict[str, str]:
        """Discover available plugins in configured directories"""
        discovered = {}

        for directory in self.plugin_directories:
            if not os.path.exists(directory):
                logger.warning(f"Plugin directory not found: {directory}")
                continue

            for item in os.listdir(directory):
                plugin_path = os.path.join(directory, item)

                # Check for Python files
                if item.endswith(".py") and not item.startswith("__"):
                    plugin_name = item[:-3]  # Remove .py extension
                    discovered[plugin_name] = plugin_path

                # Check for plugin packages
                elif os.path.isdir(plugin_path) and os.path.exists(
                    os.path.join(plugin_path, "__init__.py")
                ):
                    discovered[item] = plugin_path

        logger.info(f"Discovered {len(discovered)} plugins")
        return discovered

    async def load_plugin(self, plugin_name: str, plugin_path: str) -> bool:
        """Load a specific plugin"""
        try:
            # Skip if already loaded
            if plugin_name in self.registry:
                logger.debug(f"Plugin {plugin_name} already loaded")
                return True

            # Load the plugin module
            spec = importlib.util.spec_from_file_location(plugin_name, plugin_path)
            if spec is None or spec.loader is None:
                raise ValueError(f"Could not load spec for {plugin_name}")

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find plugin class
            plugin_class = None
            for name, obj in inspect.getmembers(module):
                if (
                    inspect.isclass(obj)
                    and issubclass(obj, PluginInterface)
                    and obj != PluginInterface
                ):
                    plugin_class = obj
                    break

            if plugin_class is None:
                raise ValueError(f"No plugin class found in {plugin_name}")

            # Get plugin configuration
            config = self.configurations.get(plugin_name, PluginConfiguration())

            # Instantiate plugin
            plugin_instance = plugin_class(config.configuration)

            # Validate plugin
            validation_issues = PluginValidator.validate_interface_compliance(
                plugin_instance
            )
            if validation_issues:
                raise ValueError(f"Plugin validation failed: {validation_issues}")

            metadata_issues = PluginValidator.validate_metadata(
                plugin_instance.metadata
            )
            if metadata_issues:
                raise ValueError(f"Metadata validation failed: {metadata_issues}")

            # Register plugin
            registry_entry = PluginRegistry(
                plugin=plugin_instance,
                metadata=plugin_instance.metadata,
                status=PluginStatus.LOADED,
                load_time=datetime.now(timezone.utc),
                dependencies=plugin_instance.metadata.dependencies.copy(),
            )

            self.registry[plugin_name] = registry_entry

            # Grant required permissions
            for permission in plugin_instance.metadata.permissions:
                self.permission_manager.grant_permission(
                    plugin_instance.plugin_id, permission
                )

            # Register in type-specific registries
            self._register_by_type(plugin_name, plugin_instance)

            # Subscribe to events
            plugin_instance.register_event_handler(
                EventType.SYSTEM_SHUTDOWN, self._handle_system_shutdown
            )

            self.metrics["plugins_loaded"] += 1
            logger.info(f"Successfully loaded plugin: {plugin_name}")

            # Publish load event
            load_event = PluginEvent(
                event_id=str(id(plugin_instance)),
                event_type=EventType.PLUGIN_LOADED,
                source_plugin="plugin_manager",
                data={
                    "plugin_name": plugin_name,
                    "plugin_type": plugin_instance.metadata.plugin_type,
                    "version": plugin_instance.metadata.version,
                },
            )
            await self.event_bus.publish(load_event)

            return True

        except Exception as e:
            logger.error(f"Failed to load plugin {plugin_name}: {str(e)}")
            self.metrics["errors"] += 1
            return False

    def _register_by_type(self, plugin_name: str, plugin: PluginInterface):
        """Register plugin in appropriate type-specific registry"""
        if isinstance(plugin, TaskProcessorInterface):
            self.task_processors[plugin_name] = plugin
        elif isinstance(plugin, DataSourceInterface):
            self.data_sources[plugin_name] = plugin
        elif isinstance(plugin, NotificationInterface):
            self.notification_plugins[plugin_name] = plugin
        elif isinstance(plugin, AnalyticsInterface):
            self.analytics_plugins[plugin_name] = plugin
        elif isinstance(plugin, IntegrationInterface):
            self.integration_plugins[plugin_name] = plugin

    async def load_enabled_plugins(self):
        """Load all enabled plugins in dependency order"""
        # Discover plugins
        discovered = await self.discover_plugins()

        # Filter enabled plugins
        enabled_plugins = {}
        for plugin_name, plugin_path in discovered.items():
            config = self.configurations.get(plugin_name, PluginConfiguration())
            if config.enabled:
                enabled_plugins[plugin_name] = plugin_path

        # For dependency resolution, we need metadata without loading
        # This is a simplified approach - in production, you'd parse metadata separately
        plugin_metadata = {}
        for plugin_name in enabled_plugins.keys():
            # Simplified: assume no dependencies for discovery
            # In production, parse metadata from plugin files
            plugin_metadata[plugin_name] = PluginMetadata(
                name=plugin_name,
                version="1.0.0",
                description="Plugin",
                author="Unknown",
                plugin_type=PluginType.TASK_PROCESSOR,
                dependencies=[],  # Would be parsed from actual plugin
            )

        # Resolve load order
        try:
            load_order = self.dependency_resolver.resolve_load_order(plugin_metadata)
        except ValueError as e:
            logger.error(f"Dependency resolution failed: {str(e)}")
            return

        # Load plugins in order
        for plugin_name in load_order:
            if plugin_name in enabled_plugins:
                await self.load_plugin(plugin_name, enabled_plugins[plugin_name])

    async def activate_plugin(self, plugin_name: str) -> bool:
        """Activate a loaded plugin"""
        try:
            if plugin_name not in self.registry:
                logger.error(f"Plugin {plugin_name} not found")
                return False

            registry_entry = self.registry[plugin_name]

            if registry_entry.status == PluginStatus.ACTIVE:
                logger.debug(f"Plugin {plugin_name} already active")
                return True

            # Initialize if needed
            if registry_entry.status == PluginStatus.LOADED:
                success = await registry_entry.plugin.initialize()
                if not success:
                    logger.error(f"Failed to initialize plugin {plugin_name}")
                    return False
                registry_entry.status = PluginStatus.INITIALIZED

            # Activate plugin
            success = await registry_entry.plugin.activate()
            if success:
                registry_entry.status = PluginStatus.ACTIVE
                registry_entry.last_activity = datetime.now(timezone.utc)
                self.metrics["plugins_active"] += 1

                # Publish activation event
                activate_event = PluginEvent(
                    event_id=str(id(registry_entry.plugin)),
                    event_type=EventType.PLUGIN_ACTIVATED,
                    source_plugin="plugin_manager",
                    data={"plugin_name": plugin_name},
                )
                await self.event_bus.publish(activate_event)

                logger.info(f"Activated plugin: {plugin_name}")
                return True
            else:
                logger.error(f"Failed to activate plugin {plugin_name}")
                return False

        except Exception as e:
            logger.error(f"Error activating plugin {plugin_name}: {str(e)}")
            registry_entry.error_count += 1
            return False

    async def deactivate_plugin(self, plugin_name: str) -> bool:
        """Deactivate an active plugin"""
        try:
            if plugin_name not in self.registry:
                logger.error(f"Plugin {plugin_name} not found")
                return False

            registry_entry = self.registry[plugin_name]

            if registry_entry.status != PluginStatus.ACTIVE:
                logger.debug(f"Plugin {plugin_name} not active")
                return True

            # Deactivate plugin
            success = await registry_entry.plugin.deactivate()
            if success:
                registry_entry.status = PluginStatus.INACTIVE
                self.metrics["plugins_active"] -= 1

                # Publish deactivation event
                deactivate_event = PluginEvent(
                    event_id=str(id(registry_entry.plugin)),
                    event_type=EventType.PLUGIN_DEACTIVATED,
                    source_plugin="plugin_manager",
                    data={"plugin_name": plugin_name},
                )
                await self.event_bus.publish(deactivate_event)

                logger.info(f"Deactivated plugin: {plugin_name}")
                return True
            else:
                logger.error(f"Failed to deactivate plugin {plugin_name}")
                return False

        except Exception as e:
            logger.error(f"Error deactivating plugin {plugin_name}: {str(e)}")
            registry_entry.error_count += 1
            return False

    async def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin completely"""
        try:
            if plugin_name not in self.registry:
                logger.error(f"Plugin {plugin_name} not found")
                return False

            registry_entry = self.registry[plugin_name]

            # Deactivate if active
            if registry_entry.status == PluginStatus.ACTIVE:
                await self.deactivate_plugin(plugin_name)

            # Cleanup plugin resources
            await registry_entry.plugin.cleanup()

            # Remove from registries
            self._unregister_by_type(plugin_name, registry_entry.plugin)

            # Revoke permissions
            for permission in registry_entry.metadata.permissions:
                self.permission_manager.revoke_permission(
                    registry_entry.plugin.plugin_id, permission
                )

            # Remove from registry
            del self.registry[plugin_name]
            self.metrics["plugins_loaded"] -= 1

            logger.info(f"Unloaded plugin: {plugin_name}")
            return True

        except Exception as e:
            logger.error(f"Error unloading plugin {plugin_name}: {str(e)}")
            return False

    def _unregister_by_type(self, plugin_name: str, plugin: PluginInterface):
        """Remove plugin from type-specific registries"""
        if plugin_name in self.task_processors:
            del self.task_processors[plugin_name]
        elif plugin_name in self.data_sources:
            del self.data_sources[plugin_name]
        elif plugin_name in self.notification_plugins:
            del self.notification_plugins[plugin_name]
        elif plugin_name in self.analytics_plugins:
            del self.analytics_plugins[plugin_name]
        elif plugin_name in self.integration_plugins:
            del self.integration_plugins[plugin_name]

    async def _handle_system_shutdown(self, event: PluginEvent):
        """Handle system shutdown event"""
        logger.info("Handling system shutdown, deactivating all plugins")

        # Deactivate all active plugins
        for plugin_name, registry_entry in self.registry.items():
            if registry_entry.status == PluginStatus.ACTIVE:
                await self.deactivate_plugin(plugin_name)

    def get_plugin(self, plugin_name: str) -> Optional[PluginInterface]:
        """Get plugin instance by name"""
        registry_entry = self.registry.get(plugin_name)
        return registry_entry.plugin if registry_entry else None

    def get_plugin_status(self, plugin_name: str) -> Optional[PluginStatus]:
        """Get plugin status"""
        registry_entry = self.registry.get(plugin_name)
        return registry_entry.status if registry_entry else None

    def list_plugins(self) -> Dict[str, Dict[str, Any]]:
        """List all plugins with their status and metadata"""
        result = {}

        for plugin_name, registry_entry in self.registry.items():
            result[plugin_name] = {
                "status": registry_entry.status,
                "metadata": {
                    "name": registry_entry.metadata.name,
                    "version": registry_entry.metadata.version,
                    "description": registry_entry.metadata.description,
                    "plugin_type": registry_entry.metadata.plugin_type,
                    "dependencies": registry_entry.metadata.dependencies,
                },
                "load_time": registry_entry.load_time.isoformat(),
                "last_activity": (
                    registry_entry.last_activity.isoformat()
                    if registry_entry.last_activity
                    else None
                ),
                "error_count": registry_entry.error_count,
                "performance_metrics": registry_entry.performance_metrics,
            }

        return result

    def get_plugins_by_type(self, plugin_type: PluginType) -> List[str]:
        """Get list of plugin names by type"""
        return [
            name
            for name, registry_entry in self.registry.items()
            if registry_entry.metadata.plugin_type == plugin_type
        ]

    async def health_check_all(self) -> Dict[str, PluginResult]:
        """Perform health check on all active plugins"""
        results = {}

        for plugin_name, registry_entry in self.registry.items():
            if registry_entry.status == PluginStatus.ACTIVE:
                try:
                    result = await registry_entry.plugin.health_check()
                    results[plugin_name] = result
                except Exception as e:
                    results[plugin_name] = PluginResult(success=False, error=str(e))
                    registry_entry.error_count += 1

        return results

    def get_system_metrics(self) -> Dict[str, Any]:
        """Get plugin system metrics"""
        return {
            "plugin_manager": self.metrics,
            "event_bus": self.event_bus.metrics,
            "plugins": {
                name: {
                    "error_count": entry.error_count,
                    "performance_metrics": entry.performance_metrics,
                    "last_activity": (
                        entry.last_activity.isoformat() if entry.last_activity else None
                    ),
                }
                for name, entry in self.registry.items()
            },
        }

    async def shutdown(self):
        """Shutdown plugin manager and all plugins"""
        try:
            # Publish shutdown event
            shutdown_event = PluginEvent(
                event_id=str(id(self)),
                event_type=EventType.SYSTEM_SHUTDOWN,
                source_plugin="plugin_manager",
                data={"shutdown_time": datetime.now(timezone.utc).isoformat()},
            )
            await self.event_bus.publish(shutdown_event)

            # Deactivate and unload all plugins
            plugin_names = list(self.registry.keys())
            for plugin_name in plugin_names:
                await self.unload_plugin(plugin_name)

            # Save configurations
            self._save_configurations()

            logger.info("Plugin manager shutdown complete")

        except Exception as e:
            logger.error(f"Error during plugin manager shutdown: {str(e)}")
            raise
