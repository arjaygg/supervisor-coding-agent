from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from supervisor_agent.config import settings
import logging

logger = logging.getLogger(__name__)

# Configure database engine with better error handling and connection pooling
try:
    if "sqlite" in settings.database_url.lower():
        # SQLite configuration
        engine = create_engine(
            settings.database_url,
            connect_args={"check_same_thread": False, "timeout": 20},
            pool_pre_ping=True,
            echo=False,
        )
    else:
        # PostgreSQL/MySQL configuration
        engine = create_engine(
            settings.database_url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    
    logger.info(f"Database engine created successfully for {settings.database_url.split('://')[0]}")
    
except Exception as e:
    logger.error(f"Failed to create database engine: {str(e)}")
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()
