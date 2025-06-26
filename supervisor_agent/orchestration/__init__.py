"""
AI Swarm Orchestration Module

This module provides advanced orchestration capabilities for multi-provider
AI agent coordination, intelligent task distribution, and resource management.
"""

from .agent_specialization_engine import (
    AgentSpecializationEngine,
    AgentSpecialty,
    SpecializationCapability,
    SpecializationScore,
    create_agent_specialization_engine
)

from .multi_provider_coordinator import (
    MultiProviderCoordinator,
    ProviderOrchestrationStrategy,
    CoordinationResult,
    create_multi_provider_coordinator
)

from .task_distribution_engine import (
    TaskDistributionEngine,
    DistributionStrategy,
    TaskSplit,
    DistributionResult,
    create_task_distribution_engine
)

__all__ = [
    "AgentSpecializationEngine",
    "AgentSpecialty", 
    "SpecializationCapability",
    "SpecializationScore",
    "create_agent_specialization_engine",
    "MultiProviderCoordinator",
    "ProviderOrchestrationStrategy",
    "CoordinationResult",
    "create_multi_provider_coordinator", 
    "TaskDistributionEngine",
    "DistributionStrategy",
    "TaskSplit",
    "DistributionResult",
    "create_task_distribution_engine"
]