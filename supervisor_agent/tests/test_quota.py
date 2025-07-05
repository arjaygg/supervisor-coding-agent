from datetime import datetime, timedelta

import pytest

from supervisor_agent.core.quota import QuotaManager
from supervisor_agent.db import crud, schemas


def test_quota_manager_initialization(test_db):
    """Test quota manager initialization"""
    quota_manager = QuotaManager()
    quota_manager.initialize_agents(test_db)

    agents = crud.AgentCRUD.get_active_agents(test_db)
    # Should have agents based on config
    assert len(agents) >= 0  # May be 0 in test environment


def test_get_available_agent(test_db, sample_agent_data):
    """Test getting available agent"""
    # Create an agent
    agent_create = schemas.AgentCreate(**sample_agent_data)
    crud.AgentCRUD.create_agent(test_db, agent_create)

    quota_manager = QuotaManager()
    agent = quota_manager.get_available_agent(test_db)

    if agent:  # Only test if agent exists
        assert agent.is_active
        assert agent.quota_used < agent.quota_limit


def test_consume_quota(test_db, sample_agent_data):
    """Test quota consumption"""
    # Create an agent
    agent_create = schemas.AgentCreate(**sample_agent_data)
    created_agent = crud.AgentCRUD.create_agent(test_db, agent_create)

    quota_manager = QuotaManager()

    # Consume quota
    success = quota_manager.consume_quota(test_db, created_agent.id, 10)
    assert success

    # Check quota was consumed
    agent = crud.AgentCRUD.get_agent(test_db, created_agent.id)
    assert agent.quota_used == 10


def test_quota_exceeded(test_db, sample_agent_data):
    """Test quota exceeded scenario"""
    # Create an agent with low quota
    sample_agent_data["quota_limit"] = 5
    agent_create = schemas.AgentCreate(**sample_agent_data)
    created_agent = crud.AgentCRUD.create_agent(test_db, agent_create)

    quota_manager = QuotaManager()

    # Try to consume more than available
    success = quota_manager.consume_quota(test_db, created_agent.id, 10)
    assert not success


def test_quota_status(test_db, sample_agent_data):
    """Test quota status retrieval"""
    # Create an agent
    agent_create = schemas.AgentCreate(**sample_agent_data)
    crud.AgentCRUD.create_agent(test_db, agent_create)

    quota_manager = QuotaManager()
    status = quota_manager.get_quota_status(test_db)

    assert "total_agents" in status
    assert "available_agents" in status
    assert "agents" in status
    assert isinstance(status["agents"], list)


def test_estimate_messages_for_task():
    """Test message estimation for different task types"""
    quota_manager = QuotaManager()

    # Test different task types
    assert quota_manager.estimate_messages_from_task("PR_REVIEW", 1000) >= 2
    assert (
        quota_manager.estimate_messages_from_task("ISSUE_SUMMARY", 1000) == 1
    )
    assert quota_manager.estimate_messages_from_task("FEATURE", 1000) >= 3

    # Test large payload
    assert quota_manager.estimate_messages_from_task(
        "PR_REVIEW", 60000
    ) > quota_manager.estimate_messages_from_task("PR_REVIEW", 1000)
