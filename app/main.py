"""
Vanna SQL Service - Main Application
Self-contained SQL generation service using Vanna AI
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .api import router
from .services import vanna_service
from .database import db_manager

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("=" * 70)
    logger.info(f"🚀 Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}")
    logger.info("=" * 70)
    
    try:
        # Initialize database
        logger.info("📊 Initializing database connection...")
        await db_manager.initialize()
        
        # Initialize Vanna
        logger.info("🤖 Initializing Vanna AI...")
        await vanna_service.initialize()
        
        logger.info("=" * 70)
        logger.info("✅ Service ready!")
        logger.info(f"📡 Listening on http://{settings.HOST}:{settings.PORT}")
        logger.info("=" * 70)
        logger.info("\n📚 API Endpoints:")
        logger.info("  POST /api/generate-sql  - Generate SQL from natural language")
        logger.info("  POST /api/query         - Generate and execute SQL")
        logger.info("  POST /api/train-schema  - Train on database schema")
        logger.info("  GET  /api/schema        - Get database schema info")
        logger.info("  GET  /api/trained-tables - Get trained tables list")
        logger.info("  GET  /health            - Health check")
        logger.info("  GET  /docs              - Interactive API documentation")
        logger.info("=" * 70)
        
        yield
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise
    
    finally:
        # Shutdown
        logger.info("🛑 Shutting down service...")
        await db_manager.close()
        logger.info("👋 Service stopped")


# Create FastAPI app
app = FastAPI(
    title=settings.SERVICE_NAME,
    description="""
    # Vanna SQL Generation Service
    
    A self-contained microservice that generates SQL queries from natural language
    using Vanna AI. Can be connected to any PostgreSQL database and trained on
    any schema.
    
    ## Features
    - 🤖 Natural language to SQL generation
    - 📊 Automatic database schema training
    - ✍️ Support for read (SELECT) and write (INSERT/UPDATE/DELETE) operations
    - 🔐 Role-based access control
    - 📦 external vector DB Qdrant needed
    - 🚀 Production-ready with connection pooling
    
    ## Quick Start
    1. Train on your schema: `POST /api/train-schema`
    2. Generate SQL: `POST /api/generate-sql`
    3. Execute queries: `POST /api/query`
    
    ## Use Cases
    - Replace hardcoded SQL queries
    - Enable natural language database queries
    - Build AI-powered analytics interfaces
    - Rapid prototyping of data applications
    """,
    version=settings.SERVICE_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "status": "running",
        "docs": "/docs",
        "health": "/health"
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "vanna_sql_service.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=True,
        log_level=settings.LOG_LEVEL.lower()
    )
