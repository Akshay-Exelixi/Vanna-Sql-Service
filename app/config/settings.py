"""
Configuration settings for Vanna SQL Service
"""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings"""
    
    # Service Configuration
    SERVICE_NAME: str = "vanna-sql-service"
    SERVICE_VERSION: str = "2.0.0"
    HOST: str = "0.0.0.0"
    PORT: int = 8010
    
    # Database Configuration
    DATABASE_URL: str
    DB_MIN_POOL_SIZE: int = 2
    DB_MAX_POOL_SIZE: int = 10
    DB_TIMEOUT: int = 30
    
    # OpenAI Configuration (for Vanna LLM)
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-5"
    LLM_TEMPERATURE: float = 0.1
    
    # Vector Database (Qdrant)
    QDRANT_URL: str = "http://hrms-qdrant:6333"  # Qdrant server URL
    QDRANT_COLLECTION: str = "vanna_hrms"  # Qdrant collection name
    QDRANT_API_KEY: Optional[str] = None  # Optional if Qdrant requires auth
    
    # Vanna Configuration
    MAX_TOOL_ITERATIONS: int = 10
    ENABLE_STREAMING: bool = False
    
    # Schema Training Configuration
    SCHEMA_NAME: str = "hrms"  # Default schema config to load (e.g., 'hrms', 'assets')
    AUTO_TRAIN_ON_STARTUP: bool = True  # Whether to train Vanna on startup
    
    # Security
    CORS_ORIGINS: str = "*"
    MAX_QUERY_RESULTS: int = 1000
    QUERY_TIMEOUT: int = 30
    ALLOWED_OPERATIONS: list = ["SELECT", "INSERT", "UPDATE", "DELETE"]
    
    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields from .env file


# Global settings instance
settings = Settings()
