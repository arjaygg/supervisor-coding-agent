import asyncio
import subprocess
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from supervisor_agent.core.agent import AgentManager, ClaudeAgentWrapper
from supervisor_agent.db.models import Task, TaskType


@pytest.fixture
def mock_task():
    """Create a mock task for testing"""
    task = Mock(spec=Task)
    task.id = 1
    task.type = TaskType.PR_REVIEW
    task.payload = {
        "repository": "test/repo",
        "pr_number": 123,
        "title": "Test PR",
        "description": "Test description",
        "diff": "test diff",
    }
    return task


def test_agent_wrapper_initialization():
    """Test agent wrapper initialization"""
    agent = ClaudeAgentWrapper("test-agent", "test-key")
    assert agent.agent_id == "test-agent"
    assert agent.api_key == "test-key"


def test_build_pr_review_prompt(mock_task):
    """Test PR review prompt building"""
    agent = ClaudeAgentWrapper("test-agent", "test-key")
    shared_memory = {"context": "test context"}

    prompt = agent._build_prompt(mock_task, shared_memory)

    assert "Task Type: PR_REVIEW" in prompt
    assert "Shared Context:" in prompt
    assert "test/repo" in prompt
    assert "Test PR" in prompt


def test_build_issue_summary_prompt():
    """Test issue summary prompt building"""
    agent = ClaudeAgentWrapper("test-agent", "test-key")

    task = Mock(spec=Task)
    task.type = TaskType.ISSUE_SUMMARY
    task.payload = {
        "title": "Test Issue",
        "description": "Issue description",
        "labels": ["bug", "high-priority"],
    }

    prompt = agent._build_prompt(task, {})

    assert "Task Type: ISSUE_SUMMARY" in prompt
    assert "Test Issue" in prompt
    assert "Issue description" in prompt


def test_build_code_analysis_prompt():
    """Test code analysis prompt building"""
    agent = ClaudeAgentWrapper("test-agent", "test-key")

    task = Mock(spec=Task)
    task.type = TaskType.CODE_ANALYSIS
    task.payload = {
        "file_path": "/path/to/file.py",
        "code": "def hello(): pass",
        "language": "python",
    }

    prompt = agent._build_prompt(task, {})

    assert "Task Type: CODE_ANALYSIS" in prompt
    assert "/path/to/file.py" in prompt
    assert "def hello(): pass" in prompt


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_execute_task_success(mock_validate_cli, mock_subprocess, mock_task):
    """Test successful task execution"""
    # Mock CLI validation to return True
    mock_validate_cli.return_value = True

    # Mock successful subprocess execution
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "Test response from Claude"
    mock_subprocess.return_value.stderr = ""

    agent = ClaudeAgentWrapper("test-agent", "test-key")
    result = await agent.execute_task(mock_task, {})

    assert result["success"] is True
    assert "Test response from Claude" in result["result"]
    assert "execution_time" in result
    assert "prompt" in result

    # Verify subprocess was called with correct arguments
    mock_subprocess.assert_called_once()
    args, kwargs = mock_subprocess.call_args
    assert args[0][0] == "/usr/local/bin/claude"  # CLI command
    assert kwargs.get("input") is not None  # Prompt sent via stdin
    assert kwargs.get("capture_output") is True
    assert kwargs.get("text") is True
    assert kwargs.get("timeout") == 300


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_execute_task_failure(mock_validate_cli, mock_subprocess, mock_task):
    """Test failed task execution - agent should fallback to mock response"""
    # Mock CLI validation to return True
    mock_validate_cli.return_value = True

    # Mock failed subprocess execution
    mock_subprocess.return_value.returncode = 1
    mock_subprocess.return_value.stdout = ""
    mock_subprocess.return_value.stderr = "Error message"

    agent = ClaudeAgentWrapper("test-agent", "test-key")
    result = await agent.execute_task(mock_task, {})

    # Agent should succeed with fallback mock response
    assert result["success"] is True
    assert "result" in result
    assert "Mock response generated" in result["result"]
    assert "execution_time" in result


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_execute_task_timeout(mock_validate_cli, mock_subprocess, mock_task):
    """Test task execution timeout - agent should fallback to mock response"""
    # Mock CLI validation to return True
    mock_validate_cli.return_value = True

    # Mock timeout exception
    mock_subprocess.side_effect = subprocess.TimeoutExpired(
        ["/usr/local/bin/claude"], 300
    )

    agent = ClaudeAgentWrapper("test-agent", "test-key")
    result = await agent.execute_task(mock_task, {})

    # Agent should succeed with fallback mock response
    assert result["success"] is True
    assert "result" in result
    assert "Mock response generated" in result["result"]
    assert "execution_time" in result


def test_agent_manager_initialization():
    """Test agent manager initialization"""
    with patch("supervisor_agent.core.agent.settings") as mock_settings:
        mock_settings.claude_api_keys_list = ["key1", "key2"]

        manager = AgentManager()

        assert len(manager.agents) == 2
        assert "claude-agent-1" in manager.agents
        assert "claude-agent-2" in manager.agents


def test_agent_manager_get_agent():
    """Test getting agent from manager"""
    with patch("supervisor_agent.core.agent.settings") as mock_settings:
        mock_settings.claude_api_keys_list = ["key1"]

        manager = AgentManager()
        agent = manager.get_agent("claude-agent-1")

        assert agent is not None
        assert agent.agent_id == "claude-agent-1"


def test_agent_manager_get_available_agent_ids():
    """Test getting available agent IDs"""
    with patch("supervisor_agent.core.agent.settings") as mock_settings:
        mock_settings.claude_api_keys_list = ["key1", "key2"]

        manager = AgentManager()
        agent_ids = manager.get_available_agent_ids()

        assert len(agent_ids) == 2
        assert "claude-agent-1" in agent_ids
        assert "claude-agent-2" in agent_ids


# New comprehensive tests for Claude CLI integration


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_command_construction(
    mock_validate_cli, mock_subprocess, mock_task
):
    """Test that Claude CLI commands are constructed correctly"""
    # Mock CLI validation to return True
    mock_validate_cli.return_value = True
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "CLI response"
    mock_subprocess.return_value.stderr = ""

    agent = ClaudeAgentWrapper("test-agent", "test-key")
    await agent.execute_task(mock_task, {})

    # Verify CLI command construction
    mock_subprocess.assert_called_once()
    args, kwargs = mock_subprocess.call_args

    # Should call claude CLI with proper arguments
    command = args[0]
    assert command[0] == "/usr/local/bin/claude"
    # Prompt is sent via stdin, not as argument
    assert kwargs.get("input") is not None

    # Environment should include API key
    env = kwargs.get("env", {})
    assert "ANTHROPIC_API_KEY" in env
    assert env["ANTHROPIC_API_KEY"] == "test-key"


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_environment_isolation(
    mock_validate_cli, mock_subprocess, mock_task
):
    """Test that each agent has isolated environment"""
    # Mock CLI validation to return True
    mock_validate_cli.return_value = True
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "Response"
    mock_subprocess.return_value.stderr = ""

    agent1 = ClaudeAgentWrapper("agent-1", "key-1")
    agent2 = ClaudeAgentWrapper("agent-2", "key-2")

    await agent1.execute_task(mock_task, {})
    await agent2.execute_task(mock_task, {})

    # Each agent should use its own API key
    calls = mock_subprocess.call_args_list
    assert len(calls) == 2

    env1 = calls[0][1].get("env", {})
    env2 = calls[1][1].get("env", {})

    assert env1["ANTHROPIC_API_KEY"] == "key-1"
    assert env2["ANTHROPIC_API_KEY"] == "key-2"


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_prompt_content(mock_validate_cli, mock_subprocess, mock_task):
    """Test that prompts contain expected content"""
    mock_validate_cli.return_value = True
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "Response"
    mock_subprocess.return_value.stderr = ""

    agent = ClaudeAgentWrapper("test-agent", "test-key")
    shared_memory = {
        "previous_result": "Some context",
        "project_info": "Test project",
    }

    await agent.execute_task(mock_task, shared_memory)

    # Extract the prompt from the CLI call
    args, kwargs = mock_subprocess.call_args

    # Prompt is sent via stdin
    prompt = kwargs.get("input")

    # Verify prompt contains expected elements
    assert "Task Type: PR_REVIEW" in prompt
    assert "test/repo" in prompt
    assert "Test PR" in prompt
    assert "Shared Context:" in prompt
    assert "previous_result: Some context" in prompt
    assert "project_info: Test project" in prompt


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_concurrent_execution(mock_validate_cli, mock_subprocess):
    """Test concurrent execution of multiple agents"""
    mock_validate_cli.return_value = True
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "Response"
    mock_subprocess.return_value.stderr = ""

    # Create multiple agents
    agent1 = ClaudeAgentWrapper("agent-1", "key-1")
    agent2 = ClaudeAgentWrapper("agent-2", "key-2")

    # Create multiple tasks
    task1 = Mock(spec=Task)
    task1.id = 1
    task1.type = TaskType.PR_REVIEW
    task1.payload = {"repository": "repo1", "pr_number": 1}

    task2 = Mock(spec=Task)
    task2.id = 2
    task2.type = TaskType.CODE_ANALYSIS
    task2.payload = {"file_path": "test.py", "code": "def test(): pass"}

    # Execute tasks concurrently
    results = await asyncio.gather(
        agent1.execute_task(task1, {}), agent2.execute_task(task2, {})
    )

    # Both should succeed
    assert len(results) == 2
    assert all(result["success"] for result in results)

    # Should have made 2 CLI calls
    assert mock_subprocess.call_count == 2


def test_claude_cli_path_configuration():
    """Test that Claude CLI path is configurable"""
    with patch("supervisor_agent.core.agent.settings") as mock_settings:
        mock_settings.claude_cli_path = "/custom/path/claude"

        agent = ClaudeAgentWrapper("test-agent", "test-key")
        assert agent.cli_path == "/custom/path/claude"


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_error_handling_details(
    mock_validate_cli, mock_subprocess, mock_task
):
    """Test detailed error handling for different CLI failures"""
    mock_validate_cli.return_value = True
    # Test different types of errors
    error_scenarios = [
        {
            "returncode": 1,
            "stderr": "Authentication failed",
            "expected": "Authentication failed",
        },
        {
            "returncode": 2,
            "stderr": "Rate limit exceeded",
            "expected": "Rate limit exceeded",
        },
        {
            "returncode": 3,
            "stderr": "Invalid request",
            "expected": "Invalid request",
        },
    ]

    agent = ClaudeAgentWrapper("test-agent", "test-key")

    for scenario in error_scenarios:
        mock_subprocess.return_value.returncode = scenario["returncode"]
        mock_subprocess.return_value.stdout = ""
        mock_subprocess.return_value.stderr = scenario["stderr"]

        result = await agent.execute_task(mock_task, {})

        # Agent should succeed with fallback mock response
        assert result["success"] is True
        assert "result" in result
        assert "Mock response generated" in result["result"]
        assert "execution_time" in result


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_output_parsing(mock_validate_cli, mock_subprocess, mock_task):
    """Test parsing of Claude CLI output"""
    mock_validate_cli.return_value = True
    # Test various output formats
    test_outputs = [
        "Simple response",
        "Multi-line\nresponse\nwith\nbreaks",
        "Response with special chars: !@#$%^&*()",
        "Very long response " + "x" * 1000,
    ]

    agent = ClaudeAgentWrapper("test-agent", "test-key")

    for output in test_outputs:
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = output
        mock_subprocess.return_value.stderr = ""

        result = await agent.execute_task(mock_task, {})

        assert result["success"] is True
        assert result["result"] == output.strip()


@pytest.mark.asyncio
@patch("supervisor_agent.core.agent.subprocess.run")
@patch("supervisor_agent.core.agent.ClaudeAgentWrapper._validate_claude_cli")
async def test_claude_cli_execution_time_tracking(
    mock_validate_cli, mock_subprocess, mock_task
):
    """Test that execution time is accurately tracked"""
    mock_validate_cli.return_value = True
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "Response"
    mock_subprocess.return_value.stderr = ""

    # Mock time to control execution time measurement
    with patch("supervisor_agent.core.agent.datetime") as mock_datetime:
        start_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(
            2024, 1, 1, 12, 0, 5, tzinfo=timezone.utc
        )  # 5 seconds later

        mock_datetime.now.side_effect = [start_time, end_time]

        agent = ClaudeAgentWrapper("test-agent", "test-key")
        result = await agent.execute_task(mock_task, {})

        assert result["success"] is True
        assert result["execution_time"] == 5


def test_prompt_template_system():
    """Test prompt template system for different task types"""
    agent = ClaudeAgentWrapper("test-agent", "test-key")

    # Test all task types have proper prompt templates
    task_types = [
        TaskType.PR_REVIEW,
        TaskType.ISSUE_SUMMARY,
        TaskType.CODE_ANALYSIS,
        TaskType.REFACTOR,
        TaskType.BUG_FIX,
        TaskType.FEATURE,
    ]

    for task_type in task_types:
        task = Mock(spec=Task)
        task.type = task_type
        task.payload = {"test": "data"}

        prompt = agent._build_prompt(task, {})

        # Each prompt should contain task type value
        task_type_value = (
            task_type.value if hasattr(task_type, "value") else str(task_type)
        )
        assert f"Task Type: {task_type_value}" in prompt
        # Should have substantial content (not just headers)
        assert len(prompt) > 100
