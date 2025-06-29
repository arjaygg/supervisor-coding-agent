"""
Enhanced Agent Manager with Multi-Provider Integration

This module provides backward compatibility with the existing AgentManager while
adding multi-provider capabilities. It acts as a bridge between the legacy
agent system and the new provider architecture.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Union

from supervisor_agent.config import settings
from supervisor_agent.core.agent import AgentManager, ClaudeAgentWrapper
from supervisor_agent.core.multi_provider_service import multi_provider_service
from supervisor_agent.core.provider_coordinator import ExecutionContext
from supervisor_agent.db.crud import AgentCRUD
from supervisor_agent.db.models import Agent, Task

logger = logging.getLogger(__name__)


class EnhancedAgentManager:
    """
    Enhanced Agent Manager that provides unified interface for both
    legacy agents and new multi-provider system.

    Maintains backward compatibility while enabling new multi-provider features.
    """

    def __init__(self, enable_multi_provider: bool = None):
        """
        Initialize the enhanced agent manager

        Args:
            enable_multi_provider: Override for multi-provider enablement
        """
        self.enable_multi_provider = (
            enable_multi_provider
            if enable_multi_provider is not None
            else settings.multi_provider_enabled
        )

        # Initialize legacy agent manager for backward compatibility
        self.legacy_manager = AgentManager()

        # Track migration status
        self._migration_mode = False
        self._provider_preferences: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"Enhanced Agent Manager initialized (multi-provider: {self.enable_multi_provider})"
        )

    async def execute_task(
        self,
        task: Task,
        agent_id: Optional[str] = None,
        shared_memory: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        prefer_provider: bool = True,
    ) -> Dict[str, Any]:
        """
        Execute a task using either legacy agents or multi-provider system

        Args:
            task: Task to execute
            agent_id: Specific agent ID to use (legacy mode)
            shared_memory: Shared memory between tasks
            context: Execution context for provider selection
            prefer_provider: Whether to prefer multi-provider system over legacy agents

        Returns:
            Task execution result
        """
        try:
            # Determine execution method based on configuration and preferences
            if self.enable_multi_provider and prefer_provider:
                return await self._execute_with_multi_provider(
                    task, context, shared_memory
                )
            elif agent_id:
                return await self._execute_with_legacy_agent(
                    task, agent_id, shared_memory
                )
            else:
                return await self._execute_with_auto_selection(
                    task, shared_memory, context
                )

        except Exception as e:
            logger.error(f"Task execution failed: {str(e)}")

            # Fallback to alternative execution method
            if self.enable_multi_provider and not prefer_provider:
                logger.info("Falling back to multi-provider system")
                return await self._execute_with_multi_provider(
                    task, context, shared_memory
                )
            else:
                logger.info("Falling back to legacy agent system")
                return await self._execute_with_legacy_agent(task, None, shared_memory)

    async def _execute_with_multi_provider(
        self,
        task: Task,
        context: Optional[Dict[str, Any]],
        shared_memory: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute task using multi-provider system"""
        logger.debug(f"Executing task {task.id} with multi-provider system")

        # Initialize multi-provider service if needed
        if not multi_provider_service.is_enabled():
            await multi_provider_service.initialize()

        # Create legacy agent processor for compatibility
        async def legacy_agent_processor(task, shared_memory):
            # This bridges the gap between new and old systems
            return await self._execute_with_legacy_agent(task, None, shared_memory)

        return await multi_provider_service.process_task(
            task=task,
            agent_processor=legacy_agent_processor,
            context=context,
            shared_memory=shared_memory,
        )

    async def _execute_with_legacy_agent(
        self,
        task: Task,
        agent_id: Optional[str],
        shared_memory: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute task using legacy agent system"""
        logger.debug(f"Executing task {task.id} with legacy agent system")

        if agent_id:
            agent = self.legacy_manager.get_agent(agent_id)
        else:
            # Use round-robin or first available agent
            available_agents = self.legacy_manager.get_available_agent_ids()
            if not available_agents:
                raise Exception("No legacy agents available")
            agent_id = available_agents[0]
            agent = self.legacy_manager.get_agent(agent_id)

        if not agent:
            raise Exception(f"Agent {agent_id} not found")

        return await agent.execute_task(task, shared_memory or {})

    async def _execute_with_auto_selection(
        self,
        task: Task,
        shared_memory: Optional[Dict[str, Any]],
        context: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Automatically select best execution method"""
        logger.debug(f"Auto-selecting execution method for task {task.id}")

        # Decision logic for execution method
        if self.enable_multi_provider:
            # Check if multi-provider system is healthy
            try:
                status = await multi_provider_service.get_provider_status()
                healthy_providers = status.get("healthy_providers", 0)

                if healthy_providers > 0:
                    return await self._execute_with_multi_provider(
                        task, context, shared_memory
                    )

            except Exception as e:
                logger.warning(f"Multi-provider system not available: {str(e)}")

        # Fallback to legacy system
        return await self._execute_with_legacy_agent(task, None, shared_memory)

    async def get_available_agents(self) -> Dict[str, Any]:
        """Get all available agents from both systems"""
        result = {
            "legacy_agents": [],
            "providers": [],
            "total_capacity": 0,
            "multi_provider_enabled": self.enable_multi_provider,
        }

        # Get legacy agents
        try:
            legacy_agent_ids = self.legacy_manager.get_available_agent_ids()
            result["legacy_agents"] = [
                {"id": agent_id, "type": "legacy_claude_agent", "status": "available"}
                for agent_id in legacy_agent_ids
            ]
            result["total_capacity"] += len(legacy_agent_ids)
        except Exception as e:
            logger.warning(f"Error getting legacy agents: {str(e)}")

        # Get multi-provider status
        if self.enable_multi_provider:
            try:
                status = await multi_provider_service.get_provider_status()
                providers = status.get("providers", {})

                for provider_id, provider_info in providers.items():
                    result["providers"].append(
                        {
                            "id": provider_id,
                            "name": provider_info.get("name", provider_id),
                            "type": provider_info.get("type", "unknown"),
                            "health_status": provider_info.get(
                                "health_status", "unknown"
                            ),
                            "health_score": provider_info.get("health_score", 0.0),
                            "capabilities": provider_info.get("capabilities", []),
                        }
                    )

                result["total_capacity"] += len(providers)

            except Exception as e:
                logger.warning(f"Error getting provider status: {str(e)}")

        return result

    async def set_provider_preference(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> bool:
        """Set provider preferences for a user"""
        try:
            self._provider_preferences[user_id] = {
                "preferred_providers": preferences.get("preferred_providers", []),
                "exclude_providers": preferences.get("exclude_providers", []),
                "routing_strategy": preferences.get("routing_strategy", "optimal"),
                "max_cost_usd": preferences.get("max_cost_usd"),
                "prefer_multi_provider": preferences.get("prefer_multi_provider", True),
                "updated_at": datetime.now(timezone.utc),
            }

            logger.info(f"Updated provider preferences for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error setting provider preferences: {str(e)}")
            return False

    async def get_provider_preference(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get provider preferences for a user"""
        return self._provider_preferences.get(user_id)

    async def migrate_to_multi_provider(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Migrate from legacy agent system to multi-provider system

        Args:
            dry_run: If True, only simulate the migration

        Returns:
            Migration plan and results
        """
        migration_plan = {
            "dry_run": dry_run,
            "legacy_agents": [],
            "provider_mappings": [],
            "migration_steps": [],
            "estimated_downtime": "< 1 minute",
            "rollback_plan": "Available",
        }

        try:
            # Analyze current legacy agents
            legacy_agent_ids = self.legacy_manager.get_available_agent_ids()

            for agent_id in legacy_agent_ids:
                agent = self.legacy_manager.get_agent(agent_id)
                migration_plan["legacy_agents"].append(
                    {
                        "id": agent_id,
                        "api_key": (
                            agent.api_key if hasattr(agent, "api_key") else "***"
                        ),
                        "status": "active",
                    }
                )

                # Create corresponding provider mapping
                provider_mapping = {
                    "legacy_agent_id": agent_id,
                    "new_provider_id": f"claude-cli-{agent_id.split('-')[-1]}",
                    "provider_type": "claude_cli",
                    "config": {
                        "api_keys": (
                            [agent.api_key] if hasattr(agent, "api_key") else []
                        ),
                        "rate_limit_per_day": 1000,
                        "priority": (
                            int(agent_id.split("-")[-1]) if "-" in agent_id else 1
                        ),
                    },
                }
                migration_plan["provider_mappings"].append(provider_mapping)

            # Define migration steps
            migration_plan["migration_steps"] = [
                "1. Initialize multi-provider service",
                "2. Register providers from legacy agents",
                "3. Test provider connectivity",
                "4. Update configuration to enable multi-provider",
                "5. Gradually migrate traffic",
                "6. Verify system health",
                "7. Decommission legacy agents (optional)",
            ]

            # Execute migration if not dry run
            if not dry_run:
                self._migration_mode = True

                # Initialize multi-provider service
                await multi_provider_service.initialize()

                # Register providers
                for mapping in migration_plan["provider_mappings"]:
                    success = await multi_provider_service.register_provider(
                        provider_id=mapping["new_provider_id"],
                        provider_type=mapping["provider_type"],
                        config=mapping["config"],
                    )

                    if success:
                        mapping["migration_status"] = "success"
                    else:
                        mapping["migration_status"] = "failed"

                migration_plan["migration_completed"] = True
                migration_plan["migration_timestamp"] = datetime.now(timezone.utc)

            return migration_plan

        except Exception as e:
            logger.error(f"Migration failed: {str(e)}")
            migration_plan["error"] = str(e)
            return migration_plan

    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health across all execution methods"""
        health = {
            "overall_status": "healthy",
            "legacy_system": {"status": "unknown", "agents": 0},
            "multi_provider_system": {"status": "unknown", "providers": 0},
            "recommendations": [],
            "timestamp": datetime.now(timezone.utc),
        }

        try:
            # Check legacy system health
            legacy_agent_ids = self.legacy_manager.get_available_agent_ids()
            health["legacy_system"] = {
                "status": "healthy" if legacy_agent_ids else "no_agents",
                "agents": len(legacy_agent_ids),
                "agent_ids": legacy_agent_ids,
            }

        except Exception as e:
            health["legacy_system"] = {"status": "error", "error": str(e), "agents": 0}

        # Check multi-provider system health
        if self.enable_multi_provider:
            try:
                status = await multi_provider_service.get_provider_status()
                health["multi_provider_system"] = {
                    "status": (
                        "healthy"
                        if status.get("healthy_providers", 0) > 0
                        else "unhealthy"
                    ),
                    "providers": status.get("total_providers", 0),
                    "healthy_providers": status.get("healthy_providers", 0),
                    "provider_details": status.get("providers", {}),
                }

            except Exception as e:
                health["multi_provider_system"] = {
                    "status": "error",
                    "error": str(e),
                    "providers": 0,
                }
        else:
            health["multi_provider_system"] = {"status": "disabled", "providers": 0}

        # Generate recommendations
        if (
            health["legacy_system"]["agents"] == 0
            and health["multi_provider_system"]["providers"] == 0
        ):
            health["overall_status"] = "critical"
            health["recommendations"].append(
                "No execution methods available - configure agents or providers"
            )

        elif health["legacy_system"]["agents"] > 0 and not self.enable_multi_provider:
            health["recommendations"].append(
                "Consider enabling multi-provider system for improved reliability"
            )

        elif (
            health["multi_provider_system"]["providers"] == 0
            and self.enable_multi_provider
        ):
            health["recommendations"].append(
                "Multi-provider enabled but no providers configured"
            )

        return health

    def get_legacy_manager(self) -> AgentManager:
        """Get the underlying legacy agent manager for backward compatibility"""
        return self.legacy_manager

    def is_migration_mode(self) -> bool:
        """Check if system is in migration mode"""
        return self._migration_mode


# Global enhanced agent manager instance
enhanced_agent_manager = EnhancedAgentManager()
