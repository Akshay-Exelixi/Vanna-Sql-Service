"""
FastAPI routes for Vanna SQL Service
"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from ..models import (
    SQLGenerationRequest,
    SQLGenerationResponse,
    SchemaTrainingRequest,
    SchemaTrainingResponse,
    HealthResponse,
    SchemaResponse,
    SchemaInfo
)
from ..services import vanna_service
from ..database import db_manager
from ..config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    db_healthy = await db_manager.is_healthy()
    
    return HealthResponse(
        status="healthy" if (db_healthy and vanna_service.initialized) else "degraded",
        service=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        timestamp=datetime.now(),
        database_connected=db_healthy,
        vanna_initialized=vanna_service.initialized,
        chroma_ready=vanna_service.initialized  # ChromaDB is embedded
    )


@router.post("/api/generate-sql", response_model=SQLGenerationResponse)
async def generate_sql(request: SQLGenerationRequest):
    """
    Generate SQL from natural language question with user context
    
    - **question**: Natural language question
    - **context**: Optional context (e.g., 'leaves', 'assets')
    - **user_id**: User's employee ID for personalized queries
    - **role**: User role for RBAC
    - **execute**: Whether to execute the generated SQL
    - **max_rows**: Maximum rows to return (if executing)
    """
    try:
        if request.execute:
            # Generate and execute
            result = await vanna_service.generate_and_execute_sql(
                question=request.question,
                context=request.context,
                role=request.role,
                user_id=request.user_id,
                max_rows=request.max_rows
            )
        else:
            # Generate only
            result = await vanna_service.generate_sql(
                question=request.question,
                context=request.context,
                role=request.role,
                user_id=request.user_id
            )
        
        if result['success']:
            # Merge service metadata with request context
            service_metadata = result.get('metadata', {})
            merged_metadata = {
                **service_metadata,  # Include security validation metadata
                "operation": result.get('operation'),
                "rows_affected": result.get('rows_affected'),
                "context": request.context,
                "requested_role": request.role  # Role passed in request (may differ from resolved)
            }
            
            return SQLGenerationResponse(
                success=True,
                sql=result.get('sql'),
                results=result.get('results'),
                row_count=result.get('row_count'),
                # Multi-query fields
                query_count=result.get('query_count'),
                query_results=result.get('query_results'),
                total_row_count=result.get('total_row_count'),
                successful_queries=result.get('successful_queries'),
                failed_queries=result.get('failed_queries'),
                operation=result.get('operation'),
                # Common fields
                execution_time=result.get('execution_time'),
                explanation=result.get('explanation'),
                metadata=merged_metadata
            )
        else:
            # Include error metadata for failed requests
            error_metadata = result.get('metadata', {})
            return SQLGenerationResponse(
                success=False,
                error=result.get('error'),
                sql=result.get('sql'),
                metadata=error_metadata
            )
            
    except Exception as e:
        logger.error(f"Error in generate_sql endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/api/train-schema", response_model=SchemaTrainingResponse)
async def train_schema(request: SchemaTrainingRequest):
    """
    Train Vanna on database schema
    
    - **schema_name**: Context name (e.g., 'leaves', 'assets')
    - **tables**: Specific tables to train on (optional)
    - **include_sample_data**: Include sample questions
    """
    try:
        result = await vanna_service.train_on_database_schema(
            tables=request.tables,
            schema_name=request.schema_name
        )
        
        if result['success']:
            return SchemaTrainingResponse(
                success=True,
                message=f"Successfully trained on {len(result['tables_trained'])} tables",
                tables_trained=result['tables_trained'],
                sample_questions=result.get('sample_questions')
            )
        else:
            return SchemaTrainingResponse(
                success=False,
                message="Training failed",
                tables_trained=[],
                error=result.get('error')
            )
            
    except Exception as e:
        logger.error(f"Error in train_schema endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/api/schema", response_model=SchemaResponse)
async def get_schema(schema_name: str = "public"):
    """Get database schema information"""
    try:
        tables = await db_manager.get_all_tables(schema_name)
        
        table_infos = []
        for table_name in tables[:20]:  # Limit to first 20 tables
            schema_info = await db_manager.get_table_schema(table_name)
            table_infos.append(SchemaInfo(
                table_name=schema_info['table_name'],
                columns=schema_info['columns'],
                row_count=schema_info.get('row_count')
            ))
        
        return SchemaResponse(
            success=True,
            schemas=[schema_name],
            tables=table_infos,
            total_tables=len(tables)
        )
        
    except Exception as e:
        logger.error(f"Error getting schema: {e}")
        return SchemaResponse(
            success=False,
            schemas=[],
            tables=[],
            total_tables=0,
            error=str(e)
        )


@router.get("/api/trained-tables")
async def get_trained_tables():
    """Get list of tables that Vanna has been trained on"""
    return {
        "success": True,
        "trained_tables": list(vanna_service.trained_tables),
        "count": len(vanna_service.trained_tables)
    }


@router.post("/api/query")
async def execute_query(request: SQLGenerationRequest):
    """
    Convenience endpoint that always executes the query
    Alias for /api/generate-sql with execute=True
    """
    request.execute = True
    return await generate_sql(request)
