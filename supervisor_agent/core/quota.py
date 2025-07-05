import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from supervisor_agent.config import settings
from supervisor_agent.db.crud import AgentCRUD
from supervisor_agent.db.database import get_db
from supervisor_agent.db.models import Agent
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class QuotaManager:
    def __init__(self):
        self.quota_limit = settings.claude_quota_limit_per_agent
        self.reset_hours = settings.claude_quota_reset_hours

    def initialize_agents(self, db: Session):
        api_keys = settings.claude_api_keys_list

        for i, api_key in enumerate(api_keys):
            agent_id = f"claude-agent-{i+1}"

            existing_agent = AgentCRUD.get_agent(db, agent_id)
            if not existing_agent:
                # Create new agent
                from supervisor_agent.db.schemas import AgentCreate

                agent_data = AgentCreate(
                    id=agent_id,
                    api_key=api_key,
                    quota_limit=self.quota_limit,
                    quota_reset_at=datetime.now(timezone.utc)
                    + timedelta(hours=self.reset_hours),
                )
                AgentCRUD.create_agent(db, agent_data)
                logger.info(
                    f"Created agent {agent_id} with quota limit {self.quota_limit}"
                )
            else:
                # Update existing agent if needed
                if existing_agent.quota_limit != self.quota_limit:
                    from supervisor_agent.db.schemas import AgentUpdate

                    update_data = AgentUpdate(quota_limit=self.quota_limit)
                    AgentCRUD.update_agent(db, agent_id, update_data)
                    logger.info(f"Updated quota limit for agent {agent_id}")

    def get_available_agent(self, db: Session) -> Optional[Agent]:
        agents = AgentCRUD.get_available_agents(db)

        if not agents:
            logger.warning("No available agents found")
            return None

        # Sort by quota usage (prefer agents with less usage)
        agents.sort(key=lambda x: x.quota_used)

        # Check if the least used agent needs quota reset
        best_agent = agents[0]
        if self._needs_quota_reset(best_agent):
            self._reset_agent_quota(db, best_agent)

        return best_agent

    def consume_quota(
        self, db: Session, agent_id: str, messages_used: int = 1
    ) -> bool:
        agent = AgentCRUD.get_agent(db, agent_id)
        if not agent:
            logger.error(f"Agent {agent_id} not found")
            return False

        # Check if quota reset is needed
        if self._needs_quota_reset(agent):
            self._reset_agent_quota(db, agent)
            agent = AgentCRUD.get_agent(db, agent_id)  # Refresh agent data

        # Check if agent has enough quota
        if agent.quota_used + messages_used > agent.quota_limit:
            logger.warning(
                f"Agent {agent_id} quota exceeded: {agent.quota_used}/{agent.quota_limit}"
            )
            return False

        # Consume quota
        from supervisor_agent.db.schemas import AgentUpdate

        update_data = AgentUpdate(
            quota_used=agent.quota_used + messages_used,
            last_used_at=datetime.now(timezone.utc),
        )
        AgentCRUD.update_agent(db, agent_id, update_data)

        logger.info(
            f"Consumed {messages_used} quota for agent {agent_id}: {agent.quota_used + messages_used}/{agent.quota_limit}"
        )
        return True

    def _needs_quota_reset(self, agent: Agent) -> bool:
        return datetime.now(timezone.utc) >= agent.quota_reset_at

    def _reset_agent_quota(self, db: Session, agent: Agent):
        from supervisor_agent.db.schemas import AgentUpdate

        update_data = AgentUpdate(
            quota_used=0,
            quota_reset_at=datetime.now(timezone.utc)
            + timedelta(hours=self.reset_hours),
        )
        AgentCRUD.update_agent(db, agent.id, update_data)
        logger.info(f"Reset quota for agent {agent.id}")

    def get_quota_status(self, db: Session) -> dict:
        agents = AgentCRUD.get_active_agents(db)

        status = {
            "total_agents": len(agents),
            "available_agents": 0,
            "agents": [],
        }

        for agent in agents:
            agent_status = {
                "id": agent.id,
                "quota_used": agent.quota_used,
                "quota_limit": agent.quota_limit,
                "quota_remaining": agent.quota_limit - agent.quota_used,
                "quota_reset_at": agent.quota_reset_at.isoformat(),
                "is_available": agent.quota_used < agent.quota_limit,
                "last_used_at": (
                    agent.last_used_at.isoformat()
                    if agent.last_used_at
                    else None
                ),
            }

            if agent_status["is_available"]:
                status["available_agents"] += 1

            status["agents"].append(agent_status)

        return status

    def are_all_agents_saturated(self, db: Session) -> bool:
        available_agents = AgentCRUD.get_available_agents(db)
        return len(available_agents) == 0

    def get_next_quota_reset(self, db: Session) -> Optional[datetime]:
        agents = AgentCRUD.get_active_agents(db)

        if not agents:
            return None

        # Find the earliest quota reset time
        next_reset = min(agent.quota_reset_at for agent in agents)
        return next_reset

    def estimate_messages_from_task(
        self, task_type: str, payload_size: int
    ) -> int:
        # Estimate messages based on task type and payload size
        base_messages = 1

        # Adjust based on task complexity
        if task_type in ["PR_REVIEW", "CODE_ANALYSIS", "REFACTOR"]:
            base_messages = 2
        elif task_type in ["FEATURE", "BUG_FIX"]:
            base_messages = 3

        # Adjust based on payload size (rough estimate)
        if payload_size > 10000:  # Large payloads
            base_messages += 1
        elif payload_size > 50000:  # Very large payloads
            base_messages += 2

        return base_messages


quota_manager = QuotaManager()
