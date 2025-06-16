#!/usr/bin/env python3
"""
Celery worker entry point for the Supervisor Agent.

This script starts the Celery worker process that executes tasks.
"""

import os
import sys

# Add the project root to Python path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from supervisor_agent.queue.celery_app import celery_app
from supervisor_agent.utils.logger import setup_logging

if __name__ == '__main__':
    # Setup logging
    setup_logging()
    
    # Start the worker
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--pool=prefork'
    ])