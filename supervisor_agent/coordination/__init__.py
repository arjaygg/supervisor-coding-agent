"""
Coordination and orchestration components for multi-agent swarm management.

This module handles intelligent coordination between agents, including
communication, task handoffs, and conflict resolution.
"""

from .swarm_coordinator import IntelligentSwarmCoordinator
from .agent_communication_hub import AgentCommunicationHub

__all__ = [
    "IntelligentSwarmCoordinator",
    "AgentCommunicationHub",
]