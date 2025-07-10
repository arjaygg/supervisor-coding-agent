"""
Function Calling Task Processor Plugin

Extensible task processor that handles function calling operations
for chat responses, enabling dynamic tool usage and AI-assisted
function execution as specified in Epic 3.2.

Features:
- Dynamic function registration and discovery
- Type-safe function calling with validation
- Context-aware function selection
- Result formatting and error handling
- Integration with chat system for interactive workflows
"""

import inspect
import json
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Type, get_type_hints

from supervisor_agent.plugins.plugin_interface import (
    PluginMetadata,
    PluginResult,
    PluginType,
    TaskProcessorInterface,
)
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class FunctionRegistry:
    """Registry for managing callable functions"""

    def __init__(self):
        self.functions: Dict[str, Dict[str, Any]] = {}

    def register_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
        required_permissions: List[str] = None,
    ):
        """Register a function for calling"""
        function_name = name or func.__name__
        
        # Extract function signature and types
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)
        
        parameters = {}
        for param_name, param in signature.parameters.items():
            param_info = {
                "type": type_hints.get(param_name, Any).__name__ if param_name in type_hints else "Any",
                "required": param.default == inspect.Parameter.empty,
                "default": param.default if param.default != inspect.Parameter.empty else None,
            }
            parameters[param_name] = param_info

        function_info = {
            "function": func,
            "name": function_name,
            "description": description or func.__doc__ or f"Function {function_name}",
            "category": category,
            "parameters": parameters,
            "return_type": type_hints.get("return", Any).__name__ if "return" in type_hints else "Any",
            "required_permissions": required_permissions or [],
            "registered_at": datetime.now(timezone.utc),
        }

        self.functions[function_name] = function_info
        logger.info(f"Registered function: {function_name} in category {category}")

    def unregister_function(self, name: str):
        """Unregister a function"""
        if name in self.functions:
            del self.functions[name]
            logger.info(f"Unregistered function: {name}")

    def get_function(self, name: str) -> Optional[Dict[str, Any]]:
        """Get function info by name"""
        return self.functions.get(name)

    def list_functions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List available functions, optionally filtered by category"""
        functions = list(self.functions.values())
        if category:
            functions = [f for f in functions if f["category"] == category]
        
        # Return safe representation without the actual function object
        return [
            {
                "name": f["name"],
                "description": f["description"],
                "category": f["category"],
                "parameters": f["parameters"],
                "return_type": f["return_type"],
                "required_permissions": f["required_permissions"],
            }
            for f in functions
        ]

    def get_function_schema(self, name: str) -> Optional[Dict[str, Any]]:
        """Get OpenAI-compatible function schema"""
        func_info = self.get_function(name)
        if not func_info:
            return None

        properties = {}
        required = []

        for param_name, param_info in func_info["parameters"].items():
            properties[param_name] = {
                "type": self._python_type_to_json_type(param_info["type"]),
                "description": f"Parameter {param_name}",
            }
            if param_info["required"]:
                required.append(param_name)

        return {
            "name": func_info["name"],
            "description": func_info["description"],
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def _python_type_to_json_type(self, python_type: str) -> str:
        """Convert Python type to JSON schema type"""
        type_mapping = {
            "str": "string",
            "int": "integer",
            "float": "number",
            "bool": "boolean",
            "list": "array",
            "dict": "object",
            "Any": "string",  # Default fallback
        }
        return type_mapping.get(python_type, "string")


class FunctionCallingProcessor(TaskProcessorInterface):
    """Task processor for handling function calling operations"""

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.function_registry = FunctionRegistry()
        self.execution_stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "average_execution_time": 0.0,
        }
        
        # Register built-in functions
        self._register_builtin_functions()

    @property
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        return PluginMetadata(
            name="function_calling_processor",
            version="1.0.0",
            description="Process function calling tasks with dynamic function registry",
            author="Supervisor Agent Team",
            plugin_type=PluginType.TASK_PROCESSOR,
            dependencies=[],
            min_api_version="1.0.0",
            max_api_version="2.0.0",
            configuration_schema={
                "max_execution_time": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds",
                    "required": False,
                    "default": 30,
                },
                "allowed_categories": {
                    "type": "array",
                    "description": "Allowed function categories",
                    "required": False,
                    "default": ["general", "utility", "chat"],
                },
                "security_mode": {
                    "type": "string",
                    "description": "Security mode: strict, moderate, permissive",
                    "required": False,
                    "default": "moderate",
                },
            },
            permissions=["function:call", "system:execute"],
            tags=["function-calling", "task-processor", "dynamic"],
        )

    async def initialize(self) -> bool:
        """Initialize the plugin"""
        try:
            logger.info("Function calling processor initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize function calling processor: {str(e)}")
            return False

    async def activate(self) -> bool:
        """Activate the plugin"""
        try:
            logger.info("Function calling processor activated successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to activate function calling processor: {str(e)}")
            return False

    async def deactivate(self) -> bool:
        """Deactivate the plugin"""
        try:
            logger.info("Function calling processor deactivated")
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate function calling processor: {str(e)}")
            return False

    async def cleanup(self) -> bool:
        """Clean up plugin resources"""
        try:
            self.function_registry.functions.clear()
            logger.info("Function calling processor cleaned up successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to cleanup function calling processor: {str(e)}")
            return False

    async def health_check(self) -> PluginResult:
        """Check plugin health status"""
        try:
            function_count = len(self.function_registry.functions)
            
            health_data = {
                "status": "healthy",
                "registered_functions": function_count,
                "execution_stats": self.execution_stats,
                "categories": list(set(
                    f["category"] for f in self.function_registry.functions.values()
                )),
            }

            return PluginResult(success=True, data=health_data)
        except Exception as e:
            return PluginResult(success=False, error=str(e))

    async def process_task(self, task_data: Dict[str, Any]) -> PluginResult:
        """Process a function calling task"""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Extract task parameters
            function_name = task_data.get("function_name")
            function_args = task_data.get("function_args", {})
            context = task_data.get("context", {})
            
            if not function_name:
                return PluginResult(
                    success=False,
                    error="Missing required parameter: function_name"
                )

            # Get function info
            func_info = self.function_registry.get_function(function_name)
            if not func_info:
                return PluginResult(
                    success=False,
                    error=f"Function not found: {function_name}"
                )

            # Validate permissions if required
            security_mode = self.get_configuration_value("security_mode", "moderate")
            if security_mode != "permissive":
                required_permissions = func_info.get("required_permissions", [])
                # In a real implementation, check against user/session permissions
                
            # Validate arguments
            validation_result = self._validate_arguments(func_info, function_args)
            if not validation_result["valid"]:
                return PluginResult(
                    success=False,
                    error=f"Invalid arguments: {validation_result['errors']}"
                )

            # Execute function
            try:
                function = func_info["function"]
                if inspect.iscoroutinefunction(function):
                    result = await function(**function_args)
                else:
                    result = function(**function_args)

                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                
                # Update stats
                self.execution_stats["total_calls"] += 1
                self.execution_stats["successful_calls"] += 1
                self._update_average_execution_time(execution_time)

                # Format result
                formatted_result = self._format_result(result, func_info)

                return PluginResult(
                    success=True,
                    data={
                        "function_name": function_name,
                        "result": formatted_result,
                        "execution_time": execution_time,
                        "context": context,
                    },
                    execution_time=execution_time
                )

            except Exception as func_error:
                execution_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.execution_stats["total_calls"] += 1
                self.execution_stats["failed_calls"] += 1
                
                error_details = {
                    "function_name": function_name,
                    "error_type": type(func_error).__name__,
                    "error_message": str(func_error),
                    "traceback": traceback.format_exc(),
                }

                logger.error(f"Function execution failed: {error_details}")
                
                return PluginResult(
                    success=False,
                    error=f"Function execution failed: {str(func_error)}",
                    metadata=error_details,
                    execution_time=execution_time
                )

        except Exception as e:
            self.execution_stats["total_calls"] += 1
            self.execution_stats["failed_calls"] += 1
            logger.error(f"Task processing failed: {str(e)}")
            return PluginResult(success=False, error=str(e))

    def can_handle_task(self, task_type: str) -> bool:
        """Determine if this plugin can handle the given task type"""
        return task_type in ["function_call", "tool_use", "api_call", "dynamic_execution"]

    def get_supported_task_types(self) -> List[str]:
        """Return list of supported task types"""
        return ["function_call", "tool_use", "api_call", "dynamic_execution"]

    def register_function(
        self,
        func: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
        category: str = "general",
        required_permissions: List[str] = None,
    ):
        """Register a new function for calling"""
        self.function_registry.register_function(
            func, name, description, category, required_permissions
        )

    def get_available_functions(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of available functions"""
        return self.function_registry.list_functions(category)

    def get_function_schemas(self) -> List[Dict[str, Any]]:
        """Get OpenAI-compatible function schemas for all registered functions"""
        schemas = []
        for func_name in self.function_registry.functions:
            schema = self.function_registry.get_function_schema(func_name)
            if schema:
                schemas.append(schema)
        return schemas

    def _validate_arguments(self, func_info: Dict[str, Any], args: Dict[str, Any]) -> Dict[str, Any]:
        """Validate function arguments against function signature"""
        errors = []
        parameters = func_info["parameters"]

        # Check required parameters
        for param_name, param_info in parameters.items():
            if param_info["required"] and param_name not in args:
                errors.append(f"Missing required parameter: {param_name}")

        # Check parameter types (basic validation)
        for param_name, value in args.items():
            if param_name in parameters:
                expected_type = parameters[param_name]["type"]
                if not self._validate_type(value, expected_type):
                    errors.append(f"Invalid type for {param_name}: expected {expected_type}")

        return {"valid": len(errors) == 0, "errors": errors}

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Basic type validation"""
        type_checks = {
            "str": lambda v: isinstance(v, str),
            "int": lambda v: isinstance(v, int),
            "float": lambda v: isinstance(v, (int, float)),
            "bool": lambda v: isinstance(v, bool),
            "list": lambda v: isinstance(v, list),
            "dict": lambda v: isinstance(v, dict),
            "Any": lambda v: True,
        }
        
        check_func = type_checks.get(expected_type, lambda v: True)
        return check_func(value)

    def _format_result(self, result: Any, func_info: Dict[str, Any]) -> Any:
        """Format function result for consistent output"""
        if result is None:
            return {"type": "null", "value": None}
        
        result_type = type(result).__name__
        
        # Handle different result types
        if isinstance(result, (str, int, float, bool)):
            return {"type": result_type, "value": result}
        elif isinstance(result, (list, tuple)):
            return {"type": "array", "value": list(result), "length": len(result)}
        elif isinstance(result, dict):
            return {"type": "object", "value": result, "keys": list(result.keys())}
        else:
            # Try to serialize complex objects
            try:
                serialized = json.dumps(result, default=str)
                return {"type": result_type, "value": serialized, "serialized": True}
            except (TypeError, ValueError):
                return {"type": result_type, "value": str(result), "string_representation": True}

    def _update_average_execution_time(self, execution_time: float):
        """Update average execution time"""
        total_calls = self.execution_stats["total_calls"]
        current_avg = self.execution_stats["average_execution_time"]
        
        # Calculate new average
        new_avg = ((current_avg * (total_calls - 1)) + execution_time) / total_calls
        self.execution_stats["average_execution_time"] = new_avg

    def _register_builtin_functions(self):
        """Register built-in utility functions"""
        
        def get_current_time() -> str:
            """Get current timestamp"""
            return datetime.now(timezone.utc).isoformat()

        def calculate_sum(numbers: List[float]) -> float:
            """Calculate sum of a list of numbers"""
            return sum(numbers)

        def format_json(data: Any) -> str:
            """Format data as JSON string"""
            return json.dumps(data, indent=2, default=str)

        def count_words(text: str) -> int:
            """Count words in text"""
            return len(text.split())

        def reverse_string(text: str) -> str:
            """Reverse a string"""
            return text[::-1]

        # Register built-in functions
        self.register_function(
            get_current_time,
            description="Get current UTC timestamp",
            category="utility"
        )
        
        self.register_function(
            calculate_sum,
            description="Calculate sum of numbers",
            category="math"
        )
        
        self.register_function(
            format_json,
            description="Format data as JSON",
            category="utility"
        )
        
        self.register_function(
            count_words,
            description="Count words in text",
            category="text"
        )
        
        self.register_function(
            reverse_string,
            description="Reverse a string",
            category="text"
        )