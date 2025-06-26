"""
Claude CLI process management and validation.
Separates CLI interaction logic from task execution.
"""
import os
import shutil
import subprocess
from typing import Optional
from supervisor_agent.config import settings
from supervisor_agent.utils.logger import get_logger

logger = get_logger(__name__)


class CLIValidationError(Exception):
    """Exception raised when CLI validation fails."""
    pass


class CLIExecutionError(Exception):
    """Exception raised when CLI execution fails."""
    pass


class CLIManager:
    """Manages Claude CLI process execution and validation."""
    
    def __init__(self, cli_path: str, api_key: str):
        self.cli_path = cli_path
        self.api_key = api_key
        self.timeout = 300  # 5 minute timeout
    
    def is_mock_mode(self) -> bool:
        """Check if we're running in mock mode."""
        return self.cli_path == "mock" or not settings.claude_api_keys
    
    def validate_cli(self) -> bool:
        """Validate that Claude CLI is available and functional."""
        try:
            # In mock mode, always return False to trigger mock responses
            if self.is_mock_mode():
                return False
            
            # Check if file exists
            if not shutil.which(self.cli_path) and not os.path.isfile(self.cli_path):
                return False
                
            # Try to run a simple help command
            process = subprocess.run(
                [self.cli_path, "--help"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return process.returncode == 0
        except Exception as e:
            logger.debug(f"CLI validation failed: {str(e)}")
            return False
    
    async def execute_cli(self, prompt: str) -> str:
        """Execute Claude CLI with the given prompt."""
        try:
            # Check if we're in mock mode or CLI is invalid
            if self.is_mock_mode() or not self.validate_cli():
                raise CLIValidationError("CLI not available or in mock mode")
            
            # Set environment variable for API key, inheriting current environment
            env = os.environ.copy()
            env["ANTHROPIC_API_KEY"] = self.api_key
            
            # Construct Claude CLI command
            # Using stdin for prompt to handle large prompts and special characters
            command = [self.cli_path]
            
            # Run Claude CLI with the prompt via stdin
            process = subprocess.run(
                command,
                input=prompt,
                capture_output=True,
                text=True,
                env=env,
                timeout=self.timeout,
            )
            
            if process.returncode != 0:
                error_msg = (
                    process.stderr.strip() if process.stderr else "Unknown error"
                )
                raise CLIExecutionError(f"Claude CLI failed: {error_msg}")
            
            return process.stdout.strip()
        
        except subprocess.TimeoutExpired:
            raise CLIExecutionError("Claude CLI execution timed out")
        except FileNotFoundError:
            raise CLIExecutionError(f"Claude CLI not found at path: {self.cli_path}")
        except CLIValidationError:
            # Re-raise validation errors
            raise
        except Exception as e:
            raise CLIExecutionError(f"Failed to execute Claude CLI: {str(e)}")
    
    def set_timeout(self, timeout: int):
        """Set the execution timeout in seconds."""
        self.timeout = timeout