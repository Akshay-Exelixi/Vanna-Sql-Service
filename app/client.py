"""
Vanna SQL Service Client

Simple Python client for interacting with the Vanna SQL Service API.
Provides easy-to-use methods for SQL generation and execution.
"""

import httpx
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import json


@dataclass
class SQLResult:
    """Result of SQL generation or execution"""
    sql: str
    success: bool
    data: Optional[List[Dict[str, Any]]] = None
    error: Optional[str] = None
    execution_time: Optional[float] = None
    rows_affected: Optional[int] = None


class VannaSQLClient:
    """Client for Vanna SQL Service"""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8010",
        timeout: float = 30.0
    ):
        """
        Initialize Vanna SQL Client
        
        Args:
            base_url: Base URL of Vanna SQL Service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    def close(self):
        """Close the HTTP client"""
        self.client.close()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check service health
        
        Returns:
            Health status information
        """
        response = self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    def generate_sql(
        self, 
        question: str,
        schema: Optional[str] = None
    ) -> SQLResult:
        """
        Generate SQL from natural language question
        
        Args:
            question: Natural language question
            schema: Optional schema name to query
        
        Returns:
            SQLResult with generated SQL
        """
        payload = {"question": question}
        if schema:
            payload["schema"] = schema
        
        response = self.client.post(
            f"{self.base_url}/api/generate-sql",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return SQLResult(
                sql=data["sql"],
                success=True
            )
        else:
            error_data = response.json()
            return SQLResult(
                sql="",
                success=False,
                error=error_data.get("detail", "Unknown error")
            )
    
    def query(
        self,
        question: str,
        schema: Optional[str] = None,
        execute: bool = True
    ) -> SQLResult:
        """
        Generate and optionally execute SQL query
        
        Args:
            question: Natural language question
            schema: Optional schema name to query
            execute: Whether to execute the query
        
        Returns:
            SQLResult with SQL and execution results
        """
        payload = {
            "question": question,
            "execute": execute
        }
        if schema:
            payload["schema"] = schema
        
        response = self.client.post(
            f"{self.base_url}/api/query",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return SQLResult(
                sql=data["sql"],
                success=data["success"],
                data=data.get("data"),
                execution_time=data.get("execution_time"),
                rows_affected=data.get("rows_affected")
            )
        else:
            error_data = response.json()
            return SQLResult(
                sql="",
                success=False,
                error=error_data.get("detail", "Unknown error")
            )
    
    def train_schema(
        self,
        schema: str = "public",
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Train Vanna on database schema
        
        Args:
            schema: Schema name (default: public)
            tables: Optional list of specific tables to train on
        
        Returns:
            Training results
        """
        payload = {"schema": schema}
        if tables:
            payload["tables"] = tables
        
        response = self.client.post(
            f"{self.base_url}/api/train-schema",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    def get_schema(
        self,
        schema: str = "public"
    ) -> Dict[str, Any]:
        """
        Get database schema information
        
        Args:
            schema: Schema name (default: public)
        
        Returns:
            Schema information
        """
        response = self.client.get(
            f"{self.base_url}/api/schema",
            params={"schema": schema}
        )
        response.raise_for_status()
        return response.json()
    
    def get_trained_tables(self) -> List[str]:
        """
        Get list of trained tables
        
        Returns:
            List of trained table names
        """
        response = self.client.get(f"{self.base_url}/api/trained-tables")
        response.raise_for_status()
        data = response.json()
        return data["trained_tables"]


# Async version of the client
class AsyncVannaSQLClient:
    """Async client for Vanna SQL Service"""
    
    def __init__(
        self, 
        base_url: str = "http://localhost:8010",
        timeout: float = 30.0
    ):
        """
        Initialize Async Vanna SQL Client
        
        Args:
            base_url: Base URL of Vanna SQL Service
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check service health"""
        response = await self.client.get(f"{self.base_url}/health")
        response.raise_for_status()
        return response.json()
    
    async def generate_sql(
        self, 
        question: str,
        schema: Optional[str] = None
    ) -> SQLResult:
        """Generate SQL from natural language question"""
        payload = {"question": question}
        if schema:
            payload["schema"] = schema
        
        response = await self.client.post(
            f"{self.base_url}/api/generate-sql",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return SQLResult(
                sql=data["sql"],
                success=True
            )
        else:
            error_data = response.json()
            return SQLResult(
                sql="",
                success=False,
                error=error_data.get("detail", "Unknown error")
            )
    
    async def query(
        self,
        question: str,
        schema: Optional[str] = None,
        execute: bool = True
    ) -> SQLResult:
        """Generate and optionally execute SQL query"""
        payload = {
            "question": question,
            "execute": execute
        }
        if schema:
            payload["schema"] = schema
        
        response = await self.client.post(
            f"{self.base_url}/api/query",
            json=payload
        )
        
        if response.status_code == 200:
            data = response.json()
            return SQLResult(
                sql=data["sql"],
                success=data["success"],
                data=data.get("data"),
                execution_time=data.get("execution_time"),
                rows_affected=data.get("rows_affected")
            )
        else:
            error_data = response.json()
            return SQLResult(
                sql="",
                success=False,
                error=error_data.get("detail", "Unknown error")
            )
    
    async def train_schema(
        self,
        schema: str = "public",
        tables: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Train Vanna on database schema"""
        payload = {"schema": schema}
        if tables:
            payload["tables"] = tables
        
        response = await self.client.post(
            f"{self.base_url}/api/train-schema",
            json=payload
        )
        response.raise_for_status()
        return response.json()
    
    async def get_schema(
        self,
        schema: str = "public"
    ) -> Dict[str, Any]:
        """Get database schema information"""
        response = await self.client.get(
            f"{self.base_url}/api/schema",
            params={"schema": schema}
        )
        response.raise_for_status()
        return response.json()
    
    async def get_trained_tables(self) -> List[str]:
        """Get list of trained tables"""
        response = await self.client.get(f"{self.base_url}/api/trained-tables")
        response.raise_for_status()
        data = response.json()
        return data["trained_tables"]


# Example usage
if __name__ == "__main__":
    # Sync example
    with VannaSQLClient("http://localhost:8010") as client:
        # Check health
        health = client.health_check()
        print(f"Service status: {health['status']}")
        
        # Train on schema
        result = client.train_schema(schema="public")
        print(f"Trained on {result['tables_trained']} tables")
        
        # Query
        result = client.query("Show me all pending leave requests")
        if result.success:
            print(f"Generated SQL: {result.sql}")
            print(f"Found {len(result.data)} rows")
            print(f"Execution time: {result.execution_time}s")
        else:
            print(f"Error: {result.error}")
