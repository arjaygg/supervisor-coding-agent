"""
Centralized logging configuration with environment variable support.
"""
import os
import logging
from pathlib import Path


def get_log_directory():
    """
    Get the log directory with fallback hierarchy:
    1. SUPERVISOR_LOG_DIR environment variable
    2. /var/log/supervisor-agent/ (if writable)
    3. /tmp/supervisor-agent-logs/ (fallback)
    """
    # Check environment variable first
    env_log_dir = os.environ.get('SUPERVISOR_LOG_DIR')
    if env_log_dir:
        log_dir = Path(env_log_dir)
        if log_dir.exists() or _create_log_dir(log_dir):
            return str(log_dir)
    
    # Try production directory
    prod_log_dir = Path('/var/log/supervisor-agent')
    if prod_log_dir.exists() or _create_log_dir(prod_log_dir):
        return str(prod_log_dir)
    
    # Fallback to tmp directory
    tmp_log_dir = Path('/tmp/supervisor-agent-logs')
    if tmp_log_dir.exists() or _create_log_dir(tmp_log_dir):
        return str(tmp_log_dir)
    
    # Last resort - current directory
    return "."


def _create_log_dir(log_dir: Path) -> bool:
    """Create log directory if it doesn't exist."""
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, PermissionError):
        return False


def get_log_file_path(log_filename: str) -> str:
    """Get full path for a log file."""
    log_dir = get_log_directory()
    return os.path.join(log_dir, log_filename)


def setup_script_logging(script_name: str, log_filename: str = None) -> logging.Logger:
    """
    Set up logging for a script with both file and console output.
    
    Args:
        script_name: Name of the script (used as logger name)
        log_filename: Optional log filename (defaults to script_name.log)
    
    Returns:
        Configured logger instance
    """
    if log_filename is None:
        log_filename = f"{script_name}.log"
    
    logger = logging.getLogger(script_name)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
    
    logger.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # File handler
    log_file_path = get_log_file_path(log_filename)
    file_handler = logging.FileHandler(log_file_path)
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger