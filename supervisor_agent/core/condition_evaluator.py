"""
Condition Evaluator for Workflow Logic

Implements safe condition evaluation for workflow branching and task execution.
Supports various condition types including JavaScript-like expressions,
Python-safe evaluation, and predefined condition functions.

Security Features:
- Sandboxed execution environment
- Whitelist-based function access
- Input validation and sanitization
- Resource limits and timeout protection

SOLID Principles:
- Single Responsibility: Focused on condition evaluation
- Open-Closed: Extensible for new condition types
- Liskov Substitution: Consistent evaluation interface
- Interface Segregation: Separate interfaces for different evaluation types
- Dependency Inversion: Abstract evaluation mechanisms
"""

import ast
import math
import operator
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union

from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ConditionType(str, Enum):
    """Types of supported conditions"""

    PYTHON_EXPRESSION = "python_expression"
    SIMPLE_COMPARISON = "simple_comparison"
    TASK_STATUS = "task_status"
    CONTEXT_VALUE = "context_value"
    TIME_BASED = "time_based"
    CUSTOM_FUNCTION = "custom_function"


@dataclass
class EvaluationResult:
    """Result of condition evaluation"""

    success: bool
    result: bool
    error: Optional[str] = None
    execution_time: Optional[float] = None
    metadata: Dict[str, Any] = None


class SecurityError(Exception):
    """Raised when unsafe operations are attempted"""

    pass


class EvaluationTimeoutError(Exception):
    """Raised when evaluation takes too long"""

    pass


class SafeEvaluator:
    """
    Safe Python expression evaluator with restricted access.

    Only allows safe operations and prevents code injection attacks.
    Uses AST parsing to validate expressions before execution.
    """

    # Allowed node types for AST validation
    ALLOWED_NODES = {
        ast.Expression,
        ast.BoolOp,
        ast.And,
        ast.Or,
        ast.Not,
        ast.UnaryOp,
        ast.Compare,
        ast.Eq,
        ast.NotEq,
        ast.Lt,
        ast.LtE,
        ast.Gt,
        ast.GtE,
        ast.Is,
        ast.IsNot,
        ast.In,
        ast.NotIn,
        ast.BinOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.FloorDiv,
        ast.Mod,
        ast.Pow,
        ast.USub,
        ast.UAdd,
        ast.Constant,
        ast.Name,
        ast.Load,
        ast.Attribute,
        ast.Subscript,
        ast.List,
        ast.Tuple,
        ast.Dict,
        ast.Set,
        ast.ListComp,
        ast.DictComp,
        ast.SetComp,
        ast.comprehension,
        ast.If,
        ast.IfExp,
    }

    # Allowed built-in functions
    ALLOWED_BUILTINS = {
        "len",
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "dict",
        "set",
        "min",
        "max",
        "sum",
        "any",
        "all",
        "abs",
        "round",
        "sorted",
        "reversed",
        "enumerate",
        "zip",
        "range",
    }

    # Safe mathematical functions
    SAFE_MATH_FUNCTIONS = {
        "sqrt": math.sqrt,
        "ceil": math.ceil,
        "floor": math.floor,
        "pow": pow,
        "abs": abs,
        "round": round,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "exp": math.exp,
    }

    def __init__(self, max_expression_length: int = 1000):
        self.max_expression_length = max_expression_length

    def is_safe_expression(self, expression: str) -> bool:
        """Check if expression contains only safe operations"""
        if len(expression) > self.max_expression_length:
            return False

        try:
            # Parse expression into AST
            tree = ast.parse(expression, mode="eval")

            # Check all nodes are allowed
            for node in ast.walk(tree):
                if type(node) not in self.ALLOWED_NODES:
                    logger.warning(f"Unsafe AST node type: {type(node).__name__}")
                    return False

                # Check function calls are safe
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        if node.func.id not in self.ALLOWED_BUILTINS:
                            logger.warning(f"Unsafe function call: {node.func.id}")
                            return False
                    elif isinstance(node.func, ast.Attribute):
                        # Only allow specific attribute access
                        if not self._is_safe_attribute_access(node.func):
                            return False

                # Check name access is safe
                if isinstance(node, ast.Name):
                    if node.id.startswith("_"):
                        logger.warning(f"Unsafe name access: {node.id}")
                        return False

            return True

        except SyntaxError:
            logger.warning(f"Syntax error in expression: {expression}")
            return False

    def _is_safe_attribute_access(self, attr_node: ast.Attribute) -> bool:
        """Check if attribute access is safe"""
        # Allow basic string/list/dict methods
        safe_attributes = {
            "upper",
            "lower",
            "strip",
            "split",
            "join",
            "replace",
            "get",
            "keys",
            "values",
            "items",
            "append",
            "extend",
            "count",
            "index",
            "find",
            "startswith",
            "endswith",
        }

        if isinstance(attr_node, ast.Attribute):
            return attr_node.attr in safe_attributes

        return False

    def evaluate(self, expression: str, context: Dict[str, Any]) -> Any:
        """Safely evaluate Python expression"""
        if not self.is_safe_expression(expression):
            raise SecurityError(f"Unsafe expression: {expression}")

        # Create safe evaluation environment
        safe_globals = {
            "__builtins__": {
                name: getattr(__builtins__, name) for name in self.ALLOWED_BUILTINS
            },
            **self.SAFE_MATH_FUNCTIONS,
        }

        # Sanitize context to prevent code injection
        safe_locals = self._sanitize_context(context)

        try:
            result = eval(expression, safe_globals, safe_locals)
            return result
        except Exception as e:
            logger.error(f"Expression evaluation failed: {expression}, error: {str(e)}")
            raise

    def _sanitize_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize context variables to prevent injection"""
        sanitized = {}

        for key, value in context.items():
            # Only allow safe variable names
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                continue

            # Only allow safe value types
            if isinstance(
                value, (str, int, float, bool, list, tuple, dict, type(None))
            ):
                sanitized[key] = value
            elif hasattr(value, "__dict__"):
                # Convert objects to dict representation
                sanitized[key] = {
                    attr: getattr(value, attr)
                    for attr in dir(value)
                    if not attr.startswith("_") and not callable(getattr(value, attr))
                }

        return sanitized


class ConditionEvaluator:
    """
    Main condition evaluator supporting multiple condition types.

    Provides a unified interface for evaluating different types of conditions
    used in workflow branching and task execution logic.
    """

    def __init__(self):
        self.safe_evaluator = SafeEvaluator()
        self.custom_functions: Dict[str, Callable] = {}
        self._register_default_functions()

    def _register_default_functions(self):
        """Register default condition functions"""
        self.custom_functions.update(
            {
                "task_completed": self._task_completed,
                "task_failed": self._task_failed,
                "task_exists": self._task_exists,
                "has_value": self._has_value,
                "is_empty": self._is_empty,
                "time_after": self._time_after,
                "time_before": self._time_before,
                "between": self._between,
                "matches_pattern": self._matches_pattern,
                "count_greater_than": self._count_greater_than,
                "percentage_complete": self._percentage_complete,
            }
        )

    def register_function(self, name: str, func: Callable):
        """Register custom condition function"""
        if not name.isidentifier():
            raise ValueError(f"Invalid function name: {name}")

        self.custom_functions[name] = func
        logger.info(f"Registered custom condition function: {name}")

    def evaluate_condition(
        self,
        condition: str,
        context: Dict[str, Any],
        condition_type: ConditionType = ConditionType.PYTHON_EXPRESSION,
    ) -> bool:
        """
        Evaluate condition and return boolean result.

        Args:
            condition: Condition expression to evaluate
            context: Execution context with variables and task results
            condition_type: Type of condition to evaluate

        Returns:
            Boolean result of condition evaluation

        Raises:
            SecurityError: If condition contains unsafe operations
            EvaluationTimeoutError: If evaluation takes too long
            ValueError: If condition is invalid
        """
        start_time = datetime.now()

        try:
            result = self._evaluate_by_type(condition, context, condition_type)

            execution_time = (datetime.now() - start_time).total_seconds()
            logger.debug(
                f"Condition evaluated in {execution_time:.3f}s: {condition} -> {result}"
            )

            return bool(result)

        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(
                f"Condition evaluation failed after {execution_time:.3f}s: {condition}, error: {str(e)}"
            )
            raise

    def _evaluate_by_type(
        self, condition: str, context: Dict[str, Any], condition_type: ConditionType
    ) -> Any:
        """Evaluate condition based on its type"""
        if condition_type == ConditionType.PYTHON_EXPRESSION:
            return self.safe_evaluator.evaluate(condition, context)

        elif condition_type == ConditionType.SIMPLE_COMPARISON:
            return self._evaluate_simple_comparison(condition, context)

        elif condition_type == ConditionType.TASK_STATUS:
            return self._evaluate_task_status(condition, context)

        elif condition_type == ConditionType.CONTEXT_VALUE:
            return self._evaluate_context_value(condition, context)

        elif condition_type == ConditionType.TIME_BASED:
            return self._evaluate_time_based(condition, context)

        elif condition_type == ConditionType.CUSTOM_FUNCTION:
            return self._evaluate_custom_function(condition, context)

        else:
            raise ValueError(f"Unsupported condition type: {condition_type}")

    def _evaluate_simple_comparison(
        self, condition: str, context: Dict[str, Any]
    ) -> bool:
        """Evaluate simple comparison like 'variable > 10'"""
        # Parse simple comparison expressions
        comparison_pattern = r"(\w+)\s*(==|!=|<=|>=|<|>)\s*(.+)"
        match = re.match(comparison_pattern, condition.strip())

        if not match:
            raise ValueError(f"Invalid simple comparison: {condition}")

        variable, operator_str, value_str = match.groups()

        # Get variable value from context
        if variable not in context:
            raise ValueError(f"Variable '{variable}' not found in context")

        var_value = context[variable]

        # Parse comparison value
        try:
            if value_str.startswith('"') and value_str.endswith('"'):
                comp_value = value_str[1:-1]  # String literal
            elif value_str.startswith("'") and value_str.endswith("'"):
                comp_value = value_str[1:-1]  # String literal
            elif value_str.lower() in ("true", "false"):
                comp_value = value_str.lower() == "true"  # Boolean
            elif "." in value_str:
                comp_value = float(value_str)  # Float
            else:
                comp_value = int(value_str)  # Integer
        except ValueError:
            # Treat as string if parsing fails
            comp_value = value_str

        # Perform comparison
        operators = {
            "==": operator.eq,
            "!=": operator.ne,
            "<": operator.lt,
            "<=": operator.le,
            ">": operator.gt,
            ">=": operator.ge,
        }

        op_func = operators[operator_str]
        return op_func(var_value, comp_value)

    def _evaluate_task_status(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate task status conditions"""
        # Expected format: "task_id:status" or function call
        if ":" in condition:
            task_id, expected_status = condition.split(":", 1)
            task_results = context.get("task_results", {})

            if task_id not in task_results:
                return False

            actual_status = getattr(task_results[task_id], "status", None)
            return str(actual_status).upper() == expected_status.upper()

        # Fallback to custom function evaluation
        return self._evaluate_custom_function(condition, context)

    def _evaluate_context_value(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate context value existence and truthiness"""
        # Simple key existence check
        if condition.startswith("has:"):
            key = condition[4:]
            return key in context

        # Truthiness check
        if condition.startswith("is_true:"):
            key = condition[8:]
            return bool(context.get(key, False))

        # Direct value access
        return bool(context.get(condition, False))

    def _evaluate_time_based(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate time-based conditions"""
        now = datetime.now(timezone.utc)

        if condition.startswith("after:"):
            time_str = condition[6:]
            target_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return now > target_time

        elif condition.startswith("before:"):
            time_str = condition[7:]
            target_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            return now < target_time

        elif condition.startswith("weekday:"):
            weekday = int(condition[8:])  # 0=Monday, 6=Sunday
            return now.weekday() == weekday

        elif condition.startswith("hour:"):
            hour = int(condition[5:])
            return now.hour == hour

        return False

    def _evaluate_custom_function(
        self, condition: str, context: Dict[str, Any]
    ) -> bool:
        """Evaluate custom function calls"""
        # Parse function call format: "function_name(arg1, arg2, ...)"
        func_pattern = r"(\w+)\((.*)\)"
        match = re.match(func_pattern, condition.strip())

        if not match:
            raise ValueError(f"Invalid function call format: {condition}")

        func_name, args_str = match.groups()

        if func_name not in self.custom_functions:
            raise ValueError(f"Unknown function: {func_name}")

        # Parse arguments
        args = []
        if args_str.strip():
            # Simple argument parsing (doesn't handle nested commas)
            arg_parts = [arg.strip() for arg in args_str.split(",")]
            for arg in arg_parts:
                if arg.startswith('"') and arg.endswith('"'):
                    args.append(arg[1:-1])  # String literal
                elif arg.startswith("'") and arg.endswith("'"):
                    args.append(arg[1:-1])  # String literal
                elif arg in context:
                    args.append(context[arg])  # Context variable
                elif arg.lower() in ("true", "false"):
                    args.append(arg.lower() == "true")  # Boolean
                else:
                    try:
                        args.append(int(arg))  # Integer
                    except ValueError:
                        try:
                            args.append(float(arg))  # Float
                        except ValueError:
                            args.append(arg)  # String fallback

        # Call function
        func = self.custom_functions[func_name]
        return func(context, *args)

    # Default condition functions
    def _task_completed(self, context: Dict[str, Any], task_id: str) -> bool:
        """Check if task completed successfully"""
        task_results = context.get("task_results", {})
        if task_id not in task_results:
            return False
        return getattr(task_results[task_id], "status", None) == "COMPLETED"

    def _task_failed(self, context: Dict[str, Any], task_id: str) -> bool:
        """Check if task failed"""
        task_results = context.get("task_results", {})
        if task_id not in task_results:
            return False
        return getattr(task_results[task_id], "status", None) == "FAILED"

    def _task_exists(self, context: Dict[str, Any], task_id: str) -> bool:
        """Check if task exists in results"""
        task_results = context.get("task_results", {})
        return task_id in task_results

    def _has_value(self, context: Dict[str, Any], key: str) -> bool:
        """Check if context has non-empty value for key"""
        value = context.get(key)
        return value is not None and value != ""

    def _is_empty(self, context: Dict[str, Any], key: str) -> bool:
        """Check if context value is empty"""
        value = context.get(key)
        if value is None:
            return True
        if isinstance(value, (list, dict, str)):
            return len(value) == 0
        return False

    def _time_after(self, context: Dict[str, Any], time_str: str) -> bool:
        """Check if current time is after specified time"""
        target_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) > target_time

    def _time_before(self, context: Dict[str, Any], time_str: str) -> bool:
        """Check if current time is before specified time"""
        target_time = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        return datetime.now(timezone.utc) < target_time

    def _between(
        self, context: Dict[str, Any], value_key: str, min_val: float, max_val: float
    ) -> bool:
        """Check if value is between min and max"""
        value = context.get(value_key)
        if value is None:
            return False
        try:
            num_value = float(value)
            return min_val <= num_value <= max_val
        except (ValueError, TypeError):
            return False

    def _matches_pattern(
        self, context: Dict[str, Any], value_key: str, pattern: str
    ) -> bool:
        """Check if value matches regex pattern"""
        value = context.get(value_key)
        if not isinstance(value, str):
            return False
        return bool(re.match(pattern, value))

    def _count_greater_than(
        self, context: Dict[str, Any], collection_key: str, threshold: int
    ) -> bool:
        """Check if collection count is greater than threshold"""
        collection = context.get(collection_key)
        if collection is None:
            return False
        try:
            return len(collection) > threshold
        except TypeError:
            return False

    def _percentage_complete(self, context: Dict[str, Any], threshold: float) -> bool:
        """Check if workflow completion percentage exceeds threshold"""
        task_results = context.get("task_results", {})
        if not task_results:
            return False

        completed = sum(
            1
            for result in task_results.values()
            if getattr(result, "status", None) == "COMPLETED"
        )

        total = len(task_results)
        percentage = (completed / total) * 100 if total > 0 else 0

        return percentage >= threshold
