"""
Plugin Interface and Framework

Defines the core plugin architecture for the Supervisor Coding Agent,
enabling extensible functionality through a standardized plugin system
as specified in Phase 1.3 of the enhancement plan.

Features:
- Type-safe plugin interfaces with versioning
- Lifecycle management (load, initialize, activate, deactivate, unload)
- Dependency resolution between plugins
- Configuration management per plugin
- Event-driven plugin communication
- Security validation and sandboxing
- Performance monitoring and metrics

SOLID Principles:
- Single Responsibility: Each interface handles specific plugin aspects
- Open-Closed: Extensible for new plugin types without modification
- Liskov Substitution: Consistent plugin interface implementations
- Interface Segregation: Focused interfaces for different plugin capabilities
- Dependency Inversion: Abstract plugin dependencies
"""

import asyncio
import importlib
import inspect
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Type, Union

import semver

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class PluginType(str, Enum):
    """Types of plugins supported by the system"""

    TASK_PROCESSOR = "task_processor"
    DATA_SOURCE = "data_source"
    NOTIFICATION = "notification"
    ANALYTICS = "analytics"
    AUTHENTICATION = "authentication"
    STORAGE = "storage"
    INTEGRATION = "integration"
    WORKFLOW = "workflow"
    MONITORING = "monitoring"


class PluginStatus(str, Enum):
    """Plugin lifecycle status"""

    UNLOADED = "unloaded"
    LOADED = "loaded"
    INITIALIZED = "initialized"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    DEPRECATED = "deprecated"


class EventType(str, Enum):
    """Plugin event types"""

    PLUGIN_LOADED = "plugin_loaded"
    PLUGIN_ACTIVATED = "plugin_activated"
    PLUGIN_DEACTIVATED = "plugin_deactivated"
    PLUGIN_ERROR = "plugin_error"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    CUSTOM = "custom"


@dataclass
class PluginMetadata:
    """Plugin metadata and configuration"""

    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    min_api_version: str = "1.0.0"
    max_api_version: str = "2.0.0"
    configuration_schema: Dict[str, Any] = field(default_factory=dict)
    permissions: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    homepage: Optional[str] = None
    documentation_url: Optional[str] = None
    support_contact: Optional[str] = None


@dataclass
class PluginEvent:
    """Event data structure for plugin communication"""

    event_id: str
    event_type: EventType
    source_plugin: Optional[str]
    target_plugin: Optional[str] = None
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PluginResult:
    """Result of plugin operation"""

    success: bool
    data: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None


class PluginInterface(ABC):
    """Base interface that all plugins must implement"""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.plugin_id = str(uuid.uuid4())
        self.status = PluginStatus.UNLOADED
        self.event_handlers: Dict[EventType, List[Callable]] = {}
        self.metrics = {
            "operations_count": 0,
            "errors_count": 0,
            "last_activity": None,
            "average_execution_time": 0.0,
        }

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the plugin with configuration"""
        pass

    @abstractmethod
    async def activate(self) -> bool:
        """Activate the plugin for use"""
        pass

    @abstractmethod
    async def deactivate(self) -> bool:
        """Deactivate the plugin"""
        pass

    @abstractmethod
    async def cleanup(self) -> bool:
        """Clean up plugin resources"""
        pass

    @abstractmethod
    async def health_check(self) -> PluginResult:
        """Check plugin health status"""
        pass

    def register_event_handler(self, event_type: EventType, handler: Callable):
        """Register an event handler for specific event types"""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def handle_event(self, event: PluginEvent) -> PluginResult:
        """Handle incoming events"""
        try:
            handlers = self.event_handlers.get(event.event_type, [])
            results = []

            for handler in handlers:
                if inspect.iscoroutinefunction(handler):
                    result = await handler(event)
                else:
                    result = handler(event)
                results.append(result)

            return PluginResult(
                success=True,
                data=results,
                metadata={"handlers_executed": len(handlers)},
            )
        except Exception as e:
            logger.error(f"Plugin {self.metadata.name} event handling failed: {str(e)}")
            self.metrics["errors_count"] += 1
            return PluginResult(success=False, error=str(e))

    def update_metrics(self, execution_time: float):
        """Update plugin performance metrics"""
        self.metrics["operations_count"] += 1
        self.metrics["last_activity"] = datetime.now(timezone.utc)

        # Update average execution time
        current_avg = self.metrics["average_execution_time"]
        count = self.metrics["operations_count"]
        self.metrics["average_execution_time"] = (
            (current_avg * (count - 1)) + execution_time
        ) / count

    def get_configuration_value(self, key: str, default: Any = None) -> Any:
        """Get configuration value with default"""
        return self.config.get(key, default)

    def validate_dependencies(self, available_plugins: List[str]) -> List[str]:
        """Validate plugin dependencies and return missing ones"""
        missing = []
        for dependency in self.metadata.dependencies:
            if dependency not in available_plugins:
                missing.append(dependency)
        return missing


class TaskProcessorInterface(PluginInterface):
    """Interface for task processing plugins"""

    @abstractmethod
    async def process_task(self, task_data: Dict[str, Any]) -> PluginResult:
        """Process a task and return results"""
        pass

    @abstractmethod
    def can_handle_task(self, task_type: str) -> bool:
        """Determine if this plugin can handle the given task type"""
        pass

    @abstractmethod
    def get_supported_task_types(self) -> List[str]:
        """Return list of supported task types"""
        pass


class DataSourceInterface(PluginInterface):
    """Interface for data source plugins"""

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to data source"""
        pass

    @abstractmethod
    async def disconnect(self) -> bool:
        """Close connection to data source"""
        pass

    @abstractmethod
    async def query(
        self, query: str, parameters: Dict[str, Any] = None
    ) -> PluginResult:
        """Execute query against data source"""
        pass

    @abstractmethod
    async def get_schema(self) -> Dict[str, Any]:
        """Get data source schema information"""
        pass


class NotificationInterface(PluginInterface):
    """Interface for notification plugins"""

    @abstractmethod
    async def send_notification(
        self,
        recipient: str,
        subject: str,
        message: str,
        priority: str = "normal",
        metadata: Dict[str, Any] = None,
    ) -> PluginResult:
        """Send notification to recipient"""
        pass

    @abstractmethod
    def get_supported_channels(self) -> List[str]:
        """Return list of supported notification channels"""
        pass

    @abstractmethod
    async def validate_recipient(self, recipient: str) -> bool:
        """Validate if recipient is reachable"""
        pass


class AnalyticsInterface(PluginInterface):
    """Interface for analytics plugins"""

    @abstractmethod
    async def collect_metrics(
        self, source: str, metrics: Dict[str, Any]
    ) -> PluginResult:
        """Collect metrics from source"""
        pass

    @abstractmethod
    async def generate_report(
        self, template: str, parameters: Dict[str, Any]
    ) -> PluginResult:
        """Generate analytics report"""
        pass

    @abstractmethod
    async def get_insights(
        self, data_range: Dict[str, Any], filters: Dict[str, Any] = None
    ) -> PluginResult:
        """Generate insights from data"""
        pass


class IntegrationInterface(PluginInterface):
    """Interface for external system integration plugins"""

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, Any]) -> PluginResult:
        """Authenticate with external system"""
        pass

    @abstractmethod
    async def sync_data(
        self, direction: str, data_type: str, filters: Dict[str, Any] = None
    ) -> PluginResult:
        """Synchronize data with external system"""
        pass

    @abstractmethod
    async def execute_action(
        self, action: str, parameters: Dict[str, Any]
    ) -> PluginResult:
        """Execute action on external system"""
        pass

    @abstractmethod
    def get_supported_actions(self) -> List[str]:
        """Return list of supported actions"""
        pass


class PluginValidator:
    """Validates plugin compliance and security"""

    @staticmethod
    def validate_metadata(metadata: PluginMetadata) -> List[str]:
        """Validate plugin metadata and return list of issues"""
        issues = []

        # Required fields
        if not metadata.name:
            issues.append("Plugin name is required")

        if not metadata.version:
            issues.append("Plugin version is required")

        # Version validation
        try:
            semver.VersionInfo.parse(metadata.version)
        except ValueError:
            issues.append(f"Invalid version format: {metadata.version}")

        # API version compatibility
        try:
            min_version = semver.VersionInfo.parse(metadata.min_api_version)
            max_version = semver.VersionInfo.parse(metadata.max_api_version)
            if min_version >= max_version:
                issues.append("min_api_version must be less than max_api_version")
        except ValueError:
            issues.append("Invalid API version format")

        return issues

    @staticmethod
    def validate_interface_compliance(plugin: PluginInterface) -> List[str]:
        """Validate that plugin implements required interface methods"""
        issues = []

        # Check required methods
        required_methods = [
            "initialize",
            "activate",
            "deactivate",
            "cleanup",
            "health_check",
            "metadata",
        ]

        for method_name in required_methods:
            if not hasattr(plugin, method_name):
                issues.append(f"Missing required method: {method_name}")
            elif not callable(getattr(plugin, method_name)):
                issues.append(f"Method {method_name} is not callable")

        return issues

    @staticmethod
    def validate_configuration_schema(
        config: Dict[str, Any], schema: Dict[str, Any]
    ) -> List[str]:
        """Validate configuration against schema"""
        issues = []

        # Basic schema validation
        for key, spec in schema.items():
            if spec.get("required", False) and key not in config:
                issues.append(f"Required configuration key missing: {key}")

            if key in config:
                expected_type = spec.get("type")
                actual_value = config[key]

                if expected_type == "string" and not isinstance(actual_value, str):
                    issues.append(f"Configuration key {key} must be a string")
                elif expected_type == "integer" and not isinstance(actual_value, int):
                    issues.append(f"Configuration key {key} must be an integer")
                elif expected_type == "boolean" and not isinstance(actual_value, bool):
                    issues.append(f"Configuration key {key} must be a boolean")

        return issues


class PluginPermissionManager:
    """Manages plugin permissions and security"""

    def __init__(self):
        self.granted_permissions: Dict[str, List[str]] = {}

    def grant_permission(self, plugin_id: str, permission: str):
        """Grant permission to plugin"""
        if plugin_id not in self.granted_permissions:
            self.granted_permissions[plugin_id] = []

        if permission not in self.granted_permissions[plugin_id]:
            self.granted_permissions[plugin_id].append(permission)
            logger.info(f"Granted permission '{permission}' to plugin {plugin_id}")

    def revoke_permission(self, plugin_id: str, permission: str):
        """Revoke permission from plugin"""
        if plugin_id in self.granted_permissions:
            if permission in self.granted_permissions[plugin_id]:
                self.granted_permissions[plugin_id].remove(permission)
                logger.info(
                    f"Revoked permission '{permission}' from plugin {plugin_id}"
                )

    def has_permission(self, plugin_id: str, permission: str) -> bool:
        """Check if plugin has specific permission"""
        return (
            plugin_id in self.granted_permissions
            and permission in self.granted_permissions[plugin_id]
        )

    def get_permissions(self, plugin_id: str) -> List[str]:
        """Get all permissions for plugin"""
        return self.granted_permissions.get(plugin_id, [])

    def validate_required_permissions(
        self, plugin_id: str, required_permissions: List[str]
    ) -> List[str]:
        """Return list of missing required permissions"""
        current_permissions = self.get_permissions(plugin_id)
        missing = []

        for permission in required_permissions:
            if permission not in current_permissions:
                missing.append(permission)

        return missing
