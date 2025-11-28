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
    role: Optional[str] = Field(None, description="User role (auto-detected from database if not provided)")
    execute: bool = Field(False, description="Whether to execute the generated SQL")
    max_rows: Optional[int] = Field(None, description="Maximum rows to return")


class SQLSecurityMetadata(BaseModel):
    """Metadata for SQL security validation"""
    security_validated: bool = Field(True, description="Whether SQL passed security validation")
    role_level: Optional[int] = Field(None, description="User's role level (1=employee, 5=admin)")
    validation_warnings: Optional[List[str]] = Field(None, description="Security warnings (non-blocking)")
    validation_errors: Optional[List[str]] = Field(None, description="Security errors (blocking)")
    modifications: Optional[List[str]] = Field(None, description="Modifications made to SQL (e.g., placeholder replacements)")


class QueryResult(BaseModel):
    """Result of a single SQL query execution"""
    query_index: int = Field(..., description="Index of this query in the batch (0-based)")
    sql: str = Field(..., description="The SQL statement that was executed")
    success: bool = Field(..., description="Whether this query executed successfully")
    rows: List[Dict[str, Any]] = Field(default_factory=list, description="Query result rows")
    row_count: int = Field(0, description="Number of rows returned")
    error: Optional[str] = Field(None, description="Error message if query failed")


class SQLGenerationResponse(BaseModel):
    """Response model for SQL generation"""
    success: bool
    sql: Optional[str] = None
    results: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="Query results (for single query execution)"
    )
    row_count: Optional[int] = Field(
        None, 
        description="Number of rows returned (for single query)"
    )
    # Multi-query support
    query_count: Optional[int] = Field(
        None, 
        description="Number of SQL statements executed (for multi-query)"
    )
    query_results: Optional[List[QueryResult]] = Field(
        None, 
        description="Results for each query (for multi-query execution)"
    )
    total_row_count: Optional[int] = Field(
        None, 
        description="Total rows across all queries (for multi-query)"
    )
    successful_queries: Optional[int] = Field(
        None, 
        description="Number of successful queries (for multi-query)"
    )
    failed_queries: Optional[int] = Field(
        None, 
        description="Number of failed queries (for multi-query)"
    )
    # Common fields
    execution_time: Optional[float] = None
    explanation: Optional[str] = None
    error: Optional[str] = None
    operation: Optional[str] = Field(
        None, 
        description="Operation type: read, write, or multi_read"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, 
        description="Response metadata including security validation info"
    )


class SchemaTrainingRequest(BaseModel):
    """Request model for training Vanna with database schema"""
    schema_name: Optional[str] = Field(None, description="Specific schema to train (e.g., 'hrms')")
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
