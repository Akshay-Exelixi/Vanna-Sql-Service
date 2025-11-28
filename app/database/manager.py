"""
Database connection and query execution manager
"""
import asyncpg
import logging
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from ..config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages PostgreSQL database connections and operations"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
        self.database_url = settings.DATABASE_URL
    
    async def initialize(self):
        """Initialize database connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=settings.DB_MIN_POOL_SIZE,
                max_size=settings.DB_MAX_POOL_SIZE,
                timeout=settings.DB_TIMEOUT,
                command_timeout=settings.QUERY_TIMEOUT
            )
            logger.info("✅ Database connection pool created")
        except Exception as e:
            logger.error(f"❌ Failed to create database pool: {e}")
            raise
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection pool closed")
    
    async def is_healthy(self) -> bool:
        """Check if database connection is healthy"""
        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    async def execute_query(
        self, 
        sql: str, 
        max_rows: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Execute SQL query and return results"""
        try:
            async with self.pool.acquire() as conn:
                # Apply row limit if specified
                if max_rows:
                    sql = self._add_limit_clause(sql, max_rows)
                
                # Execute query
                rows = await conn.fetch(sql)
                
                # Convert to list of dicts
                results = [dict(row) for row in rows]
                
                logger.info(f"Query executed successfully. Rows returned: {len(results)}")
                return results
                
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise
    
    async def execute_multiple_queries(
        self,
        sql_statements: List[str],
        max_rows: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple SQL statements and return results for each.
        
        Args:
            sql_statements: List of SQL statements to execute
            max_rows: Maximum rows per query result
            
        Returns:
            List of result objects, one per query
        """
        results = []
        
        async with self.pool.acquire() as conn:
            for idx, sql in enumerate(sql_statements):
                sql = sql.strip()
                if not sql:
                    continue
                    
                query_result = {
                    "query_index": idx,
                    "sql": sql,
                    "success": False,
                    "rows": [],
                    "row_count": 0,
                    "error": None
                }
                
                try:
                    # Apply row limit if specified
                    if max_rows:
                        sql = self._add_limit_clause(sql, max_rows)
                    
                    # Execute query
                    rows = await conn.fetch(sql)
                    
                    # Convert to list of dicts
                    query_result["rows"] = [dict(row) for row in rows]
                    query_result["row_count"] = len(query_result["rows"])
                    query_result["success"] = True
                    
                    logger.info(f"Query {idx+1} executed successfully. Rows: {query_result['row_count']}")
                    
                except Exception as e:
                    logger.error(f"Query {idx+1} execution failed: {e}")
                    query_result["error"] = str(e)
                
                results.append(query_result)
        
        return results
    
    async def execute_write_query(
        self,
        sql: str
    ) -> Dict[str, Any]:
        """Execute INSERT/UPDATE/DELETE query"""
        try:
            async with self.pool.acquire() as conn:
                # For INSERT with RETURNING
                if "RETURNING" in sql.upper():
                    result = await conn.fetch(sql)
                    return {
                        "success": True,
                        "rows_affected": len(result),
                        "returning": [dict(row) for row in result]
                    }
                else:
                    # For UPDATE/DELETE
                    result = await conn.execute(sql)
                    # Extract row count from result status
                    rows_affected = int(result.split()[-1]) if result else 0
                    return {
                        "success": True,
                        "rows_affected": rows_affected
                    }
        except Exception as e:
            logger.error(f"Write query execution failed: {e}")
            raise
    
    async def get_table_schema(self, table_name: str) -> Dict[str, Any]:
        """Get schema information for a table"""
        try:
            async with self.pool.acquire() as conn:
                # Get columns
                columns = await conn.fetch("""
                    SELECT 
                        column_name,
                        data_type,
                        is_nullable,
                        column_default,
                        character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name = $1
                    ORDER BY ordinal_position
                """, table_name)
                
                # Get row count
                count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
                
                return {
                    "table_name": table_name,
                    "columns": [dict(col) for col in columns],
                    "row_count": count
                }
        except Exception as e:
            logger.error(f"Failed to get schema for {table_name}: {e}")
            return {
                "table_name": table_name,
                "columns": [],
                "row_count": 0,
                "error": str(e)
            }
    
    async def get_all_tables(self, schema: str = "public") -> List[str]:
        """Get list of all tables in schema"""
        try:
            async with self.pool.acquire() as conn:
                tables = await conn.fetch("""
                    SELECT table_name 
                    FROM information_schema.tables
                    WHERE table_schema = $1 
                    AND table_type = 'BASE TABLE'
                    ORDER BY table_name
                """, schema)
                return [table['table_name'] for table in tables]
        except Exception as e:
            logger.error(f"Failed to get tables list: {e}")
            return []
    
    async def get_table_ddl(self, table_name: str) -> str:
        """Generate CREATE TABLE statement for a table"""
        try:
            schema_info = await self.get_table_schema(table_name)
            
            if not schema_info.get('columns'):
                return f"-- Table {table_name} not found"
            
            ddl = f"CREATE TABLE {table_name} (\n"
            column_defs = []
            
            for col in schema_info['columns']:
                col_def = f"    {col['column_name']} {col['data_type']}"
                
                if col.get('character_maximum_length'):
                    col_def += f"({col['character_maximum_length']})"
                
                if col['is_nullable'] == 'NO':
                    col_def += " NOT NULL"
                
                if col.get('column_default'):
                    col_def += f" DEFAULT {col['column_default']}"
                
                column_defs.append(col_def)
            
            ddl += ",\n".join(column_defs)
            ddl += "\n);"
            
            return ddl
            
        except Exception as e:
            logger.error(f"Failed to generate DDL for {table_name}: {e}")
            return f"-- Error generating DDL: {str(e)}"
    
    def _add_limit_clause(self, sql: str, limit: int) -> str:
        """Add LIMIT clause to SQL query if not present"""
        sql_upper = sql.upper()
        if "LIMIT" not in sql_upper:
            # Handle queries with/without semicolon
            sql = sql.rstrip(';')
            sql += f" LIMIT {limit}"
        return sql
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for database transactions"""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                yield conn


# Global database manager instance
db_manager = DatabaseManager()
