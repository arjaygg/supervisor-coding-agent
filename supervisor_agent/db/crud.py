"""
CRUD operations using the new repository pattern.
This file now imports from repositories.py to maintain backward compatibility
while using the DRY-compliant repository pattern under the hood.
"""

# Import the backward compatibility wrappers from repositories
from supervisor_agent.db.repositories import (
    TaskCRUD,
    TaskSessionCRUD, 
    AgentCRUD,
    AuditLogCRUD,
    # Also export the repository instances for direct use
    task_repository,
    task_session_repository,
    agent_repository,
    audit_log_repository,
    cost_tracking_repository,
    provider_repository
)

# Re-export for backward compatibility
__all__ = [
    'TaskCRUD',
    'TaskSessionCRUD', 
    'AgentCRUD',
    'AuditLogCRUD',
    'task_repository',
    'task_session_repository',
    'agent_repository',
    'audit_log_repository',
    'cost_tracking_repository',
    'provider_repository'
]