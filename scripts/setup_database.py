#!/usr/bin/env python3
"""
Database setup script for development.
Creates all tables without migrations for easier testing with SQLite.
"""
import logging
import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from supervisor_agent.config import settings
from supervisor_agent.db.database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_database():
    """Create all database tables."""
    try:
        logger.info(f"Setting up database with URL: {settings.database_url}")

        # Import all models to ensure they're registered with Base
        import supervisor_agent.core.analytics_models
        import supervisor_agent.core.workflow_models
        from supervisor_agent.db import models

        # Create all tables
        Base.metadata.create_all(bind=engine)

        logger.info("Database setup completed successfully!")

        # List created tables
        from sqlalchemy import inspect

        inspector = inspect(engine)
        tables = inspector.get_table_names()
        logger.info(f"Created tables: {', '.join(tables)}")

        return True

    except Exception as e:
        logger.error(f"Database setup failed: {str(e)}")
        return False


if __name__ == "__main__":
    success = setup_database()
    sys.exit(0 if success else 1)
