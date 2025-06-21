from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from sqlalchemy import text
from supervisor_agent.config import settings
from supervisor_agent.api.routes.tasks import router as tasks_router
from supervisor_agent.api.routes.health import router as health_router
from supervisor_agent.api.routes.analytics import router as analytics_router
from supervisor_agent.api.routes.workflows import router as workflows_router
from supervisor_agent.api.websocket import websocket_endpoint
from supervisor_agent.api.websocket_analytics import router as analytics_ws_router
from supervisor_agent.db.database import engine
from supervisor_agent.db.models import Base
from supervisor_agent.core.quota import quota_manager
from supervisor_agent.db.database import get_db
from supervisor_agent.utils.logger import setup_logging, get_logger


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    setup_logging()
    logger = get_logger(__name__)
    logger.info("Starting Supervisor Agent API")
    
    # Log configuration info
    config_info = settings.get_startup_info()
    logger.info(f"Configuration: {config_info}")
    
    # Log configuration warnings
    warnings = settings.validate_configuration()
    if warnings:
        for warning in warnings:
            logger.warning(f"Configuration: {warning}")

    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise

    # Initialize agents in database
    from supervisor_agent.db.database import SessionLocal
    db = SessionLocal()
    try:
        # Test database connection
        db.execute(text("SELECT 1"))
        quota_manager.initialize_agents(db)
        logger.info("Agents initialized in database")
    except Exception as e:
        logger.error(f"Failed to initialize agents: {str(e)}")
        logger.warning("Application will start but some features may not work properly")
    finally:
        db.close()

    yield

    # Shutdown
    logger.info("Shutting down Supervisor Agent API")


app = FastAPI(
    title="Supervisor Coding Agent",
    description="AI-powered task orchestration and management system",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware - Allow frontend dev server and production domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",
        "http://localhost:3000",  # Alternative dev port
        "http://127.0.0.1:3000",
        "*"  # Allow all origins in development - restrict in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language", 
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers"
    ],
)

# Include routers
app.include_router(tasks_router, prefix="/api/v1", tags=["tasks"])
app.include_router(health_router, prefix="/api/v1", tags=["health"])
app.include_router(analytics_router, prefix="/api/v1", tags=["analytics"])
app.include_router(workflows_router, prefix="/api/v1", tags=["workflows"])
app.include_router(analytics_ws_router, tags=["analytics-websocket"])


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger = get_logger(__name__)
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "error": str(exc)}
    )


@app.websocket("/ws")
async def websocket_route(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await websocket_endpoint(websocket)


@app.get("/")
async def root():
    return {
        "message": "Supervisor Coding Agent API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "websocket_url": "/ws",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "supervisor_agent.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
        log_level=settings.log_level.lower(),
    )
