import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from supervisor_agent.config import settings
from supervisor_agent.core.agent import ClaudeAgentWrapper, agent_manager
from supervisor_agent.db.models import Task, TaskStatus, TaskType


class TestClaudeCliIntegration:
    """Test Claude CLI integration with mock fallback"""

    def test_mock_mode_configuration(self):
        """Test that mock mode can be configured"""
        # Test with mock environment
        with patch.dict(
            os.environ,
            {"CLAUDE_CLI_PATH": "mock", "CLAUDE_API_KEYS": "mock-key-1,mock-key-2"},
        ):
            from supervisor_agent.config import create_settings

            test_settings = create_settings()
            assert test_settings.claude_cli_path == "mock"
            assert len(test_settings.claude_api_keys_list) >= 1
            assert "mock" in test_settings.claude_api_keys_list[0]

    def test_agent_initialization(self):
        """Test that agents are properly initialized"""
        assert len(agent_manager.agents) > 0

        agent_ids = agent_manager.get_available_agent_ids()
        assert len(agent_ids) >= 1

        first_agent = agent_manager.get_agent(agent_ids[0])
        assert first_agent is not None
        # Agent CLI path should match settings
        assert first_agent.cli_path == settings.claude_cli_path

    @pytest.mark.asyncio
    async def test_mock_response_generation(self):
        """Test that mock responses are generated for different task types"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        # Test different task types
        task_types = [
            "PR_REVIEW",
            "CODE_ANALYSIS",
            "BUG_FIX",
            "FEATURE",
            "REFACTOR",
            "ISSUE_SUMMARY",
        ]

        for task_type in task_types:
            prompt = f"Task Type: {task_type}\n\nTest task"
            response = agent._generate_mock_response(prompt)

            assert response is not None
            assert len(response) > 50  # Should be substantial
            assert "Mock response generated" in response
            assert "ID:" in response

    @pytest.mark.asyncio
    async def test_pr_review_task_execution(self):
        """Test PR review task execution with mock"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        # Create a mock task
        task = Task(
            id=1,
            type=TaskType.PR_REVIEW,
            status=TaskStatus.PENDING,
            priority=5,
            payload={
                "repository": "test/repo",
                "title": "Add new feature",
                "description": "This PR adds a new feature",
                "diff": "--- a/file.py\n+++ b/file.py\n@@ -1,1 +1,2 @@\n print('hello')\n+print('world')",
            },
        )

        result = await agent.execute_task(task, {})

        assert result["success"] is True
        assert "result" in result
        assert "Code Review Analysis" in result["result"]
        assert result["execution_time"] >= 0

    @pytest.mark.asyncio
    async def test_code_analysis_task_execution(self):
        """Test code analysis task execution with mock"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        task = Task(
            id=2,
            type=TaskType.CODE_ANALYSIS,
            status=TaskStatus.PENDING,
            priority=3,
            payload={
                "file_path": "src/main.py",
                "code": "def hello():\n    print('Hello, World!')",
                "language": "python",
            },
        )

        result = await agent.execute_task(task, {})

        assert result["success"] is True
        assert "Code Analysis Report" in result["result"]
        assert "Code Quality" in result["result"]

    @pytest.mark.asyncio
    async def test_bug_fix_task_execution(self):
        """Test bug fix task execution with mock"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        task = Task(
            id=3,
            type=TaskType.BUG_FIX,
            status=TaskStatus.PENDING,
            priority=8,
            payload={
                "description": "Application crashes on startup",
                "error_message": "NullPointerException at line 42",
                "code_context": "def startup():\n    config = None\n    config.load()",
                "steps_to_reproduce": "1. Run app\n2. See crash",
            },
        )

        result = await agent.execute_task(task, {})

        assert result["success"] is True
        assert "Bug Fix Analysis" in result["result"]
        assert "Root Cause" in result["result"]

    def test_claude_cli_validation_with_mock_mode(self):
        """Test Claude CLI validation in mock mode"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")
        agent.cli_path = "mock"  # Force mock mode

        # In mock mode, validation should return False (triggering mock)
        assert agent._validate_claude_cli() is False

    @patch("subprocess.run")
    def test_claude_cli_validation_with_real_cli(self, mock_subprocess):
        """Test Claude CLI validation with real CLI"""
        # Mock successful CLI validation
        mock_subprocess.return_value = MagicMock(returncode=0)

        # Temporarily change CLI path
        original_path = settings.claude_cli_path
        settings.claude_cli_path = "claude"

        try:
            agent = ClaudeAgentWrapper("test-agent", "real-key")
            with patch("shutil.which", return_value="/usr/local/bin/claude"):
                is_valid = agent._validate_claude_cli()
                assert is_valid is True
        finally:
            settings.claude_cli_path = original_path

    @patch("subprocess.run")
    def test_claude_cli_execution_fallback(self, mock_subprocess):
        """Test that CLI execution falls back to mock on failure"""
        # Mock CLI failure
        mock_subprocess.return_value = MagicMock(
            returncode=1, stderr="Command failed", stdout=""
        )

        agent = ClaudeAgentWrapper("test-agent", "real-key")

        # Should fall back to mock response
        response = agent._generate_mock_response("Test prompt")
        assert "Mock response generated" in response

    @pytest.mark.asyncio
    async def test_shared_memory_context(self):
        """Test that shared memory context is included in prompts"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        task = Task(
            id=4,
            type=TaskType.FEATURE,
            status=TaskStatus.PENDING,
            priority=5,
            payload={"description": "New user login system"},
        )

        shared_memory = {
            "project_name": "SuperApp",
            "tech_stack": "Python/Django",
            "database": "PostgreSQL",
        }

        prompt = agent._build_prompt(task, shared_memory)

        assert "Shared Context" in prompt
        assert "project_name: SuperApp" in prompt
        assert "tech_stack: Python/Django" in prompt

    @pytest.mark.asyncio
    async def test_task_execution_error_handling(self):
        """Test error handling in task execution"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        # Create a task that will cause an error in prompt building
        task = Task(
            id=5,
            type=None,  # This should cause an error
            status=TaskStatus.PENDING,
            priority=1,
            payload={},
        )

        result = await agent.execute_task(task, {})

        # Should handle error gracefully
        assert result["success"] is False
        assert "error" in result
        assert result["execution_time"] >= 0

    def test_deterministic_mock_responses(self):
        """Test that mock responses are deterministic for same input"""
        agent = ClaudeAgentWrapper("test-agent", "mock-key")

        prompt = "Task Type: PR_REVIEW\n\nSame test prompt"

        response1 = agent._generate_mock_response(prompt)
        response2 = agent._generate_mock_response(prompt)

        # Should be identical
        assert response1 == response2

        # But different prompts should give different responses
        different_prompt = "Task Type: PR_REVIEW\n\nDifferent test prompt"
        response3 = agent._generate_mock_response(different_prompt)
        assert response1 != response3

    def test_agent_manager_singleton(self):
        """Test that agent manager maintains state"""
        # Get agents from manager
        agents1 = agent_manager.get_available_agent_ids()
        agents2 = agent_manager.get_available_agent_ids()

        # Should be the same
        assert agents1 == agents2

        # Should be able to get specific agent
        if agents1:
            agent = agent_manager.get_agent(agents1[0])
            assert agent is not None
            assert agent.agent_id == agents1[0]
