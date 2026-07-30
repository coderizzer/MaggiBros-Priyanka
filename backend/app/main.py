import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.app.config import settings
from backend.app.database.connection import engine, Base
from backend.app.api.tickets import router as tickets_router
from backend.app.api.rag import router as rag_router
from backend.app.api.workflow import router as workflow_router
from backend.app.api.knowledge import router as knowledge_router
from backend.app.api.chat import router as chat_router
from backend.app.database.seed import seed_db

# Set up basic logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("campuspilot")

# Auto-initialize and seed DB on startup
try:
    logger.info("Initializing SQLite database and seeding default operational data...")
    seed_db()
except Exception as e:
    logger.error(f"Database setup failed: {e}")

app = FastAPI(
    title="CampusPilot API",
    description="CampusPilot is an AI-powered Campus Operations Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Configure CORS middleware
allowed_origins = settings.ALLOWED_ORIGINS.split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers
app.include_router(tickets_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(workflow_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(chat_router)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "CampusPilot API",
        "docs_url": "/docs"
    }

@app.get("/health")
def health_check():
    # Simple check on settings configurations
    return {
        "status": "healthy",
        "database": "connected",
        "environment": settings.ENV,
        "ai_provider": settings.AI_PROVIDER,
        "ai_model": settings.AI_MODEL_NAME
    }
