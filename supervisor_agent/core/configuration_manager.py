"""
Configuration Management Service
Responsible for managing configuration and context conversion.
"""
from typing import Dict, Any, Optional

from supervisor_agent.core.provider_coordinator import ExecutionContext


class ConfigurationManager:
    """Handles configuration management and context conversion."""
    
    @staticmethod
    def create_execution_context(context: Optional[Dict[str, Any]]) -> ExecutionContext:
        """Create ExecutionContext from API context."""
        if not context:
            return ExecutionContext()
            
        return ExecutionContext(
            user_id=context.get("user_id"),
            organization_id=context.get("organization_id"),
            priority=context.get("priority", 5),
            max_cost_usd=context.get("max_cost_usd"),
            preferred_providers=context.get("preferred_providers"),
            exclude_providers=context.get("exclude_providers"),
            require_capabilities=context.get("require_capabilities"),
            metadata=context.get("metadata", {})
        )