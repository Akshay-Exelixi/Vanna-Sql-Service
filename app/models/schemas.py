"""
Pydantic models for API requests and responses
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class SQLGenerationRequest(BaseModel):
    """Request model for SQL generation"""
    question: str = Field(..., description="Natural language question")
    context: Optional[str] = Field(None, description="Database context hint")
    user_id: Optional[str] = Field(None, description="User ID for access control")
    role: Optional[str] = Field("employee", description="User role")
    execute: bool = Field(False, description="Whether to execute the generated SQL")
    max_rows: Optional[int] = Field(None, description="Maximum rows to return")


class SQLGenerationResponse(BaseModel):
    """Response model for SQL generation"""
    success: bool
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = None
    execution_time: Optional[float] = None
    explanation: Optional[str] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SchemaTrainingRequest(BaseModel):
    """Request model for training Vanna with database schema"""
    schema_name: Optional[str] = Field(None, description="Specific schema to train (e.g., 'leaves', 'assets')")
    tables: Optional[List[str]] = Field(None, description="Specific tables to train")
    include_sample_data: bool = Field(True, description="Include sample queries")


class SchemaTrainingResponse(BaseModel):
    """Response model for schema training"""
    success: bool
    message: str
    tables_trained: List[str]
    sample_questions: Optional[List[str]] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    service: str
    version: str
    timestamp: datetime
    database_connected: bool
    vanna_initialized: bool
    chroma_ready: bool


class SchemaInfo(BaseModel):
    """Database schema information"""
    table_name: str
    columns: List[Dict[str, Any]]
    row_count: Optional[int] = None


class SchemaResponse(BaseModel):
    """Response for schema listing"""
    success: bool
    schemas: List[str]
    tables: List[SchemaInfo]
    total_tables: int
    error: Optional[str] = None
