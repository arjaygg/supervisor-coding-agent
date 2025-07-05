"""
Coordination and orchestration components for multi-agent swarm management.

This module handles intelligent coordination between agents, including
communication, task handoffs, and conflict resolution.
"""

from .agent_collaboration_engine import AgentCollaborationEngine
from .swarm_coordinator import IntelligentSwarmCoordinator

__all__ = [
    "IntelligentSwarmCoordinator",
    "AgentCollaborationEngine",
]
