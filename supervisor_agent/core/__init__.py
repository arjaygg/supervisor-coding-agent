"""
Core module exports for supervisor agent.

This module provides the main interfaces for:
- Multi-provider coordination and management
- Intelligent task processing with provider selection
- Advanced subscription intelligence across providers
- Provider health monitoring and failover
"""

# Existing exports
from .agent import ClaudeAgentWrapper, AgentManager
from .intelligent_task_processor import IntelligentTaskProcessor
from .subscription_intelligence import SubscriptionIntelligence

# New multi-provider exports
from .provider_coordinator import (
    ProviderCoordinator, 
    ExecutionContext, 
    TaskAffinityStrategy,
    TaskAffinityTracker
)
from .multi_provider_subscription_intelligence import (
    MultiProviderSubscriptionIntelligence,
    QuotaStatus,
    ProviderQuotaInfo,
    CrossProviderAnalytics
)
from .multi_provider_task_processor import (
    MultiProviderTaskProcessor,
    TaskPriority,
    RoutingStrategy,
    TaskBatch
)

__all__ = [
    # Legacy exports (maintained for backward compatibility)
    "ClaudeAgentWrapper",
    "AgentManager", 
    "IntelligentTaskProcessor",
    "SubscriptionIntelligence",
    
    # Multi-provider architecture exports
    "ProviderCoordinator",
    "ExecutionContext",
    "TaskAffinityStrategy", 
    "TaskAffinityTracker",
    "MultiProviderSubscriptionIntelligence",
    "QuotaStatus",
    "ProviderQuotaInfo",
    "CrossProviderAnalytics",
    "MultiProviderTaskProcessor",
    "TaskPriority",
    "RoutingStrategy",
    "TaskBatch"
]