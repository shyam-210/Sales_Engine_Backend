"""
Autonomous Sales Intelligence Engine
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global MongoDB client
mongo_client: AsyncIOMotorClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events."""
    global mongo_client
    settings = get_settings()
    
    # Startup
    logger.info("Starting Sales Intelligence Engine...")
    mongo_client = AsyncIOMotorClient(settings.mongo_url)
    
    # Verify MongoDB connection
    try:
        await mongo_client.admin.command('ping')
        logger.info("MongoDB connected successfully")
    except Exception as e:
        logger.error(f"MongoDB connection failed: {e}")
        raise
    
    logger.info(f"Sales Intelligence Engine {settings.app_version} is ready")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Sales Intelligence Engine...")
    if mongo_client:
        mongo_client.close()
    logger.info("Shutdown complete")


# Initialize FastAPI application
app = FastAPI(
    title="Autonomous Sales Intelligence Engine",
    description=(
        "AI-powered sales intelligence for Zoho SalesIQ. "
        "Converts chat visitors into revenue using LLM analysis."
    ),
    version=get_settings().app_version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from app.routers import intelligence
app.include_router(intelligence.router)

# Mount static files (for agent widget and home page)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def root():
    """Health check endpoint."""
    settings = get_settings()
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "operational",
        "groq_model": settings.groq_model,
    }


@app.get("/health")
async def health_check():
    """Detailed health check with dependencies."""
    settings = get_settings()
    
    # Check MongoDB
    mongo_status = "unknown"
    try:
        await mongo_client.admin.command('ping')
        mongo_status = "connected"
    except Exception as e:
        mongo_status = f"error: {str(e)}"
    
    # Check Groq API key
    groq_configured = bool(settings.groq_api_key)
    
    return {
        "service": "Sales Intelligence Engine",
        "version": settings.app_version,
        "status": "healthy",
        "dependencies": {
            "mongodb": mongo_status,
            "groq_api": "configured" if groq_configured else "missing",
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info"
    )
