"""
Database Enums Module

Centralized enum definitions to avoid circular imports.
Shared enums used across models and schemas.
"""

from enum import Enum, IntEnum


class TaskType(str, Enum):
    """Types of tasks that can be processed"""
    PR_REVIEW = "PR_REVIEW"
    ISSUE_SUMMARY = "ISSUE_SUMMARY"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    REFACTOR = "REFACTOR"
    BUG_FIX = "BUG_FIX"
    FEATURE = "FEATURE"
    DOCUMENTATION = "DOCUMENTATION"
    TESTING = "TESTING"
    DEPLOYMENT = "DEPLOYMENT"
    SECURITY_AUDIT = "SECURITY_AUDIT"


class TaskStatus(str, Enum):
    """Status of task execution"""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class TaskPriority(IntEnum):
    """Task priority levels"""
    LOW = 1
    NORMAL = 5
    HIGH = 7
    URGENT = 9
    CRITICAL = 10


class ChatThreadStatus(str, Enum):
    """Status of chat threads"""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    COMPLETED = "COMPLETED"
    DELETED = "DELETED"


class MessageRole(str, Enum):
    """Role of message sender"""
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageType(str, Enum):
    """Type of message content"""
    TEXT = "TEXT"
    CODE = "CODE"
    IMAGE = "IMAGE"
    FILE = "FILE"
    TASK_BREAKDOWN = "TASK_BREAKDOWN"
    PROGRESS = "PROGRESS"
    NOTIFICATION = "NOTIFICATION"
    ERROR = "ERROR"


class NotificationType(str, Enum):
    """Type of notification"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"
    TASK_COMPLETE = "TASK_COMPLETE"
    TASK_FAILED = "TASK_FAILED"
    AGENT_UPDATE = "AGENT_UPDATE"
    SYSTEM_ALERT = "SYSTEM_ALERT"


class ProviderType(str, Enum):
    """Types of providers"""
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    ANTHROPIC_API = "anthropic_api"
    GOOGLE = "GOOGLE"
    COHERE = "COHERE"
    HUGGINGFACE = "HUGGINGFACE"
    CLAUDE_CLI = "claude_cli"
    LOCAL = "LOCAL"
    LOCAL_MOCK = "local_mock"
    CUSTOM = "custom"


class ProviderStatus(str, Enum):
    """Status of providers"""
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DEGRADED = "DEGRADED"
    MAINTENANCE = "MAINTENANCE"
    ERROR = "ERROR"
