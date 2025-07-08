"""
Tests for Enhanced Agent Manager integration functionality.

Tests the backward compatibility bridge between legacy agents and
multi-provider system, including migration tools and dual execution paths.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from supervisor_agent.core.agent import AgentManager
from supervisor_agent.core.enhanced_agent_manager import EnhancedAgentManager
from supervisor_agent.db.models import Task, TaskType


@pytest.fixture
def mock_legacy_manager():
    """Create a mock legacy agent manager"""
    manager = Mock(spec=AgentManager)
    manager.get_available_agent_ids = Mock(
        return_value=["claude-agent-1", "claude-agent-2"]
    )

    mock_agent = Mock()
    mock_agent.execute_task = AsyncMock(
        return_value={
            "success": True,
            "result": "Legacy agent response",
            "execution_time": 2.5,
            "execution_time_ms": 2500,
        }
    )
    manager.get_agent = Mock(return_value=mock_agent)

    return manager


@pytest.fixture
def sample_task():
    """Create a sample task for testing"""
    task = Mock(spec=Task)
    task.id = 123
    task.type = TaskType.PR_REVIEW
    task.payload = {"test": "data"}
    task.retry_count = 0
    return task


@pytest.fixture
def enhanced_manager(mock_legacy_manager):
    """Create enhanced agent manager with mocked dependencies"""
    with patch(
        "supervisor_agent.core.enhanced_agent_manager.AgentManager",
        return_value=mock_legacy_manager,
    ):
        manager = EnhancedAgentManager(enable_multi_provider=False)
        return manager


@pytest.fixture
def enhanced_manager_with_providers(mock_legacy_manager):
    """Create enhanced agent manager with multi-provider enabled"""
    with patch(
        "supervisor_agent.core.enhanced_agent_manager.AgentManager",
        return_value=mock_legacy_manager,
    ):
        manager = EnhancedAgentManager(enable_multi_provider=True)
        return manager


class TestEnhancedAgentManagerInitialization:
    """Test enhanced agent manager initialization"""

    def test_initialization_default_settings(self, mock_legacy_manager):
        """Test initialization with default settings"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.settings"
        ) as mock_settings:
            mock_settings.multi_provider_enabled = True

            with patch(
                "supervisor_agent.core.enhanced_agent_manager.AgentManager",
                return_value=mock_legacy_manager,
            ):
                manager = EnhancedAgentManager()

                assert manager.enable_multi_provider is True
                assert manager.legacy_manager == mock_legacy_manager
                assert manager._migration_mode is False

    def test_initialization_override_settings(self, mock_legacy_manager):
        """Test initialization with override settings"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.AgentManager",
            return_value=mock_legacy_manager,
        ):
            manager = EnhancedAgentManager(enable_multi_provider=False)

            assert manager.enable_multi_provider is False
            assert manager.legacy_manager == mock_legacy_manager


class TestTaskExecution:
    """Test task execution functionality"""

    @pytest.mark.asyncio
    async def test_execute_task_legacy_only(self, enhanced_manager, sample_task):
        """Test task execution with legacy agents only"""
        shared_memory = {"context": "test"}

        result = await enhanced_manager.execute_task(
            sample_task, agent_id="claude-agent-1", shared_memory=shared_memory
        )

        assert result["success"] is True
        assert "result" in result
        enhanced_manager.legacy_manager.get_agent.assert_called_with("claude-agent-1")

    @pytest.mark.asyncio
    async def test_execute_task_with_multi_provider(
        self, enhanced_manager_with_providers, sample_task
    ):
        """Test task execution with multi-provider system"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.is_enabled.return_value = True
            mock_service.process_task = AsyncMock(
                return_value={
                    "success": True,
                    "result": "Multi-provider response",
                    "provider_id": "claude-primary",
                }
            )

            result = await enhanced_manager_with_providers.execute_task(
                sample_task, prefer_provider=True
            )

            assert result["success"] is True
            assert "provider_id" in result
            mock_service.process_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_auto_selection(
        self, enhanced_manager_with_providers, sample_task
    ):
        """Test automatic selection between execution methods"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.get_provider_status = AsyncMock(
                return_value={"healthy_providers": 2, "total_providers": 2}
            )
            mock_service.is_enabled.return_value = True
            mock_service.process_task = AsyncMock(
                return_value={
                    "success": True,
                    "result": "Auto-selected multi-provider",
                }
            )

            result = await enhanced_manager_with_providers.execute_task(
                sample_task, prefer_provider=False
            )

            assert result["success"] is True
            mock_service.get_provider_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_task_fallback_on_failure(
        self, enhanced_manager_with_providers, sample_task
    ):
        """Test fallback to alternative execution method on failure"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            # First attempt fails
            mock_service.is_enabled.return_value = True
            mock_service.process_task = AsyncMock(
                side_effect=Exception("Provider failure")
            )

            result = await enhanced_manager_with_providers.execute_task(
                sample_task, prefer_provider=True
            )

            # Should fallback to legacy system
            assert result["success"] is True
            assert result["result"] == "Legacy agent response"


class TestAgentAvailability:
    """Test agent availability functionality"""

    @pytest.mark.asyncio
    async def test_get_available_agents_legacy_only(self, enhanced_manager):
        """Test getting available agents from legacy system only"""
        result = await enhanced_manager.get_available_agents()

        assert "legacy_agents" in result
        assert "providers" in result
        assert "total_capacity" in result
        assert result["multi_provider_enabled"] is False
        assert len(result["legacy_agents"]) == 2
        assert result["total_capacity"] == 2

    @pytest.mark.asyncio
    async def test_get_available_agents_with_providers(
        self, enhanced_manager_with_providers
    ):
        """Test getting available agents with multi-provider system"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.get_provider_status = AsyncMock(
                return_value={
                    "providers": {
                        "claude-primary": {
                            "name": "Claude Primary",
                            "type": "claude_cli",
                            "health_status": "healthy",
                            "health_score": 0.95,
                            "capabilities": ["code_review", "bug_fix"],
                        }
                    }
                }
            )

            result = await enhanced_manager_with_providers.get_available_agents()

            assert result["multi_provider_enabled"] is True
            assert len(result["providers"]) == 1
            assert result["providers"][0]["name"] == "Claude Primary"
            assert result["total_capacity"] == 3  # 2 legacy + 1 provider


class TestProviderPreferences:
    """Test provider preference management"""

    @pytest.mark.asyncio
    async def test_set_provider_preference(self, enhanced_manager_with_providers):
        """Test setting provider preferences for a user"""
        preferences = {
            "preferred_providers": ["claude-primary"],
            "exclude_providers": [],
            "routing_strategy": "fastest",
            "max_cost_usd": 1.0,
        }

        result = await enhanced_manager_with_providers.set_provider_preference(
            "user-123", preferences
        )

        assert result is True
        stored_prefs = await enhanced_manager_with_providers.get_provider_preference(
            "user-123"
        )
        assert stored_prefs is not None
        assert stored_prefs["preferred_providers"] == ["claude-primary"]
        assert stored_prefs["routing_strategy"] == "fastest"

    @pytest.mark.asyncio
    async def test_get_nonexistent_provider_preference(
        self, enhanced_manager_with_providers
    ):
        """Test getting preferences for non-existent user"""
        result = await enhanced_manager_with_providers.get_provider_preference(
            "nonexistent-user"
        )
        assert result is None


class TestMigration:
    """Test migration functionality"""

    @pytest.mark.asyncio
    async def test_migrate_to_multi_provider_dry_run(self, enhanced_manager):
        """Test migration planning (dry run)"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.initialize = AsyncMock()
            mock_service.register_provider = AsyncMock(return_value=True)

            result = await enhanced_manager.migrate_to_multi_provider(dry_run=True)

            assert result["dry_run"] is True
            assert "legacy_agents" in result
            assert "provider_mappings" in result
            assert "migration_steps" in result
            assert len(result["legacy_agents"]) == 2
            assert len(result["provider_mappings"]) == 2
            assert "migration_completed" not in result

    @pytest.mark.asyncio
    async def test_migrate_to_multi_provider_execute(self, enhanced_manager):
        """Test actual migration execution"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.initialize = AsyncMock()
            mock_service.register_provider = AsyncMock(return_value=True)

            result = await enhanced_manager.migrate_to_multi_provider(dry_run=False)

            assert result["dry_run"] is False
            assert result["migration_completed"] is True
            assert enhanced_manager._migration_mode is True
            mock_service.initialize.assert_called_once()
            assert mock_service.register_provider.call_count == 2


class TestSystemHealth:
    """Test system health monitoring"""

    @pytest.mark.asyncio
    async def test_get_system_health_legacy_only(self, enhanced_manager):
        """Test system health with legacy agents only"""
        result = await enhanced_manager.get_system_health()

        assert "overall_status" in result
        assert "legacy_system" in result
        assert "multi_provider_system" in result
        assert "recommendations" in result
        assert result["legacy_system"]["agents"] == 2
        assert result["multi_provider_system"]["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_get_system_health_with_providers(
        self, enhanced_manager_with_providers
    ):
        """Test system health with multi-provider system"""
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.get_provider_status = AsyncMock(
                return_value={
                    "healthy_providers": 2,
                    "total_providers": 2,
                    "providers": {},
                }
            )

            result = await enhanced_manager_with_providers.get_system_health()

            assert result["multi_provider_system"]["status"] == "healthy"
            assert result["multi_provider_system"]["providers"] == 2
            assert result["multi_provider_system"]["healthy_providers"] == 2

    @pytest.mark.asyncio
    async def test_get_system_health_critical_status(
        self, enhanced_manager_with_providers
    ):
        """Test system health when no execution methods available"""
        # Mock no legacy agents
        enhanced_manager_with_providers.legacy_manager.get_available_agent_ids = Mock(
            return_value=[]
        )

        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            mock_service.get_provider_status = AsyncMock(
                return_value={"healthy_providers": 0, "total_providers": 0}
            )

            result = await enhanced_manager_with_providers.get_system_health()

            assert result["overall_status"] == "critical"
            assert any(
                "No execution methods available" in rec
                for rec in result["recommendations"]
            )


class TestUtilityMethods:
    """Test utility methods"""

    def test_get_legacy_manager(self, enhanced_manager):
        """Test getting the underlying legacy manager"""
        legacy_manager = enhanced_manager.get_legacy_manager()
        assert legacy_manager == enhanced_manager.legacy_manager

    def test_is_migration_mode(self, enhanced_manager):
        """Test migration mode checking"""
        assert enhanced_manager.is_migration_mode() is False

        enhanced_manager._migration_mode = True
        assert enhanced_manager.is_migration_mode() is True


@pytest.mark.asyncio
async def test_integration_workflow(mock_legacy_manager):
    """Test complete integration workflow"""
    with patch(
        "supervisor_agent.core.enhanced_agent_manager.AgentManager",
        return_value=mock_legacy_manager,
    ):
        with patch(
            "supervisor_agent.core.enhanced_agent_manager.multi_provider_service"
        ) as mock_service:
            # Initialize manager
            manager = EnhancedAgentManager(enable_multi_provider=True)

            # Mock multi-provider service
            mock_service.is_enabled.return_value = True
            mock_service.get_provider_status = AsyncMock(
                return_value={"healthy_providers": 1, "total_providers": 1}
            )
            mock_service.process_task = AsyncMock(
                return_value={
                    "success": True,
                    "result": "Integration test success",
                }
            )

            # Create test task
            task = Mock(spec=Task)
            task.id = 999
            task.type = TaskType.CODE_ANALYSIS

            # Test execution
            result = await manager.execute_task(task)
            assert result["success"] is True

            # Test system health
            health = await manager.get_system_health()
            assert health["overall_status"] in ["healthy", "critical"]

            # Test agent availability
            agents = await manager.get_available_agents()
            assert agents["total_capacity"] >= 2
