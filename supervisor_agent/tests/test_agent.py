import pytest
from unittest.mock import Mock, patch, AsyncMock
from supervisor_agent.core.agent import ClaudeAgentWrapper, AgentManager
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
        "diff": "test diff"
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
        "labels": ["bug", "high-priority"]
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
        "language": "python"
    }
    
    prompt = agent._build_prompt(task, {})
    
    assert "Task Type: CODE_ANALYSIS" in prompt
    assert "/path/to/file.py" in prompt
    assert "def hello(): pass" in prompt


@patch('supervisor_agent.core.agent.subprocess.run')
async def test_execute_task_success(mock_subprocess, mock_task):
    """Test successful task execution"""
    # Mock successful subprocess execution
    mock_subprocess.return_value.returncode = 0
    mock_subprocess.return_value.stdout = "Test response from Claude"
    mock_subprocess.return_value.stderr = ""
    
    agent = ClaudeAgentWrapper("test-agent", "test-key")
    result = await agent.execute_task(mock_task, {})
    
    assert result["success"] is True
    assert "Test response from Claude" in result["result"]
    assert "execution_time" in result


@patch('supervisor_agent.core.agent.subprocess.run')
async def test_execute_task_failure(mock_subprocess, mock_task):
    """Test failed task execution"""
    # Mock failed subprocess execution
    mock_subprocess.return_value.returncode = 1
    mock_subprocess.return_value.stdout = ""
    mock_subprocess.return_value.stderr = "Error message"
    
    agent = ClaudeAgentWrapper("test-agent", "test-key")
    result = await agent.execute_task(mock_task, {})
    
    assert result["success"] is False
    assert "error" in result


@patch('supervisor_agent.core.agent.subprocess.run')
async def test_execute_task_timeout(mock_subprocess, mock_task):
    """Test task execution timeout"""
    # Mock timeout exception
    mock_subprocess.side_effect = TimeoutError("Command timed out")
    
    agent = ClaudeAgentWrapper("test-agent", "test-key")
    result = await agent.execute_task(mock_task, {})
    
    assert result["success"] is False
    assert "error" in result


def test_agent_manager_initialization():
    """Test agent manager initialization"""
    with patch('supervisor_agent.core.agent.settings') as mock_settings:
        mock_settings.claude_api_keys_list = ["key1", "key2"]
        
        manager = AgentManager()
        
        assert len(manager.agents) == 2
        assert "claude-agent-1" in manager.agents
        assert "claude-agent-2" in manager.agents


def test_agent_manager_get_agent():
    """Test getting agent from manager"""
    with patch('supervisor_agent.core.agent.settings') as mock_settings:
        mock_settings.claude_api_keys_list = ["key1"]
        
        manager = AgentManager()
        agent = manager.get_agent("claude-agent-1")
        
        assert agent is not None
        assert agent.agent_id == "claude-agent-1"


def test_agent_manager_get_available_agent_ids():
    """Test getting available agent IDs"""
    with patch('supervisor_agent.core.agent.settings') as mock_settings:
        mock_settings.claude_api_keys_list = ["key1", "key2"]
        
        manager = AgentManager()
        agent_ids = manager.get_available_agent_ids()
        
        assert len(agent_ids) == 2
        assert "claude-agent-1" in agent_ids
        assert "claude-agent-2" in agent_ids