"""
Database Enums Module

Centralized enum definitions to avoid circular imports.
All database-related enums are defined here and imported by other modules.
"""

from enum import Enum


class TaskType(str, Enum):
    """Task types supported by the system"""
    PR_REVIEW = "PR_REVIEW"
    ISSUE_SUMMARY = "ISSUE_SUMMARY"
    CODE_ANALYSIS = "CODE_ANALYSIS"
    REFACTOR = "REFACTOR"
    BUG_FIX = "BUG_FIX"
    FEATURE = "FEATURE"


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRY = "RETRY"


class ChatThreadStatus(str, Enum):
    """Chat thread status"""
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class MessageRole(str, Enum):
    """Message roles in chat"""
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    SYSTEM = "SYSTEM"


class MessageType(str, Enum):
    """Message types"""
    TEXT = "TEXT"
    CODE = "CODE"
    IMAGE = "IMAGE"
    FILE = "FILE"


class NotificationType(str, Enum):
    """Notification types"""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class ProviderType(str, Enum):
    """AI Provider types"""
    OPENAI = "OPENAI"
    ANTHROPIC = "ANTHROPIC"
    GOOGLE = "GOOGLE"
    COHERE = "COHERE"
    HUGGINGFACE = "HUGGINGFACE"
    LOCAL = "LOCAL"


class ProviderStatus(str, Enum):
    """Provider health status"""
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    INACTIVE = "INACTIVE"
    ERROR = "ERROR"