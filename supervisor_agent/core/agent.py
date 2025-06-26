from typing import Dict, Any, Optional
from supervisor_agent.config import settings
from supervisor_agent.db.models import Task
from supervisor_agent.core.task_executor import TaskExecutor
from supervisor_agent.core.prompt_builder import PromptBuilder
from supervisor_agent.core.cli_manager import CLIManager
from supervisor_agent.core.mock_response_generator import MockResponseGenerator
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeAgentWrapper:
    """Simplified agent wrapper using dependency injection for separated concerns."""
    
    def __init__(self, agent_id: str, api_key: str):
        self.agent_id = agent_id
        self.api_key = api_key
        self.cli_path = settings.claude_cli_path
        
        # Initialize components using dependency injection
        self.cli_manager = CLIManager(self.cli_path, self.api_key)
        self.prompt_builder = PromptBuilder()
        self.mock_generator = MockResponseGenerator()
        self.task_executor = TaskExecutor(
            agent_id=self.agent_id,
            cli_manager=self.cli_manager,
            prompt_builder=self.prompt_builder,
            mock_generator=self.mock_generator
        )

    async def execute_task(
        self, task: Task, shared_memory: Dict[str, Any], db_session=None
    ) -> Dict[str, Any]:
        """Execute task using the injected TaskExecutor."""
        return await self.task_executor.execute_task(task, shared_memory, db_session)


class AgentManager:
    def __init__(self):
        self.agents: Dict[str, ClaudeAgentWrapper] = {}
        self._initialize_agents()

    def _initialize_agents(self):
        api_keys = settings.claude_api_keys_list

        for i, api_key in enumerate(api_keys):
            agent_id = f"claude-agent-{i+1}"
            self.agents[agent_id] = ClaudeAgentWrapper(agent_id, api_key)

            logger.info(f"Initialized agent {agent_id}")

    def get_agent(self, agent_id: str) -> Optional[ClaudeAgentWrapper]:
        return self.agents.get(agent_id)

    def get_available_agent_ids(self) -> list[str]:
        return list(self.agents.keys())


agent_manager = AgentManager()
