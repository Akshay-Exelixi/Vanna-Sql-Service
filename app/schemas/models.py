"""
Pydantic models for YAML schema configuration
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class ColumnConfig(BaseModel):
    """Configuration for a table column with semantic descriptions"""
    description: Optional[str] = Field(None, description="Human-readable description of the column")
    type: Optional[str] = Field(None, description="Data type hint (e.g., uuid, timestamp)")
    allowed_values: Optional[List[str]] = Field(None, description="Allowed values for enum-like columns")
    is_foreign_key: Optional[bool] = Field(False, description="Whether this column is a foreign key")
    references: Optional[str] = Field(None, description="Referenced table.column for foreign keys")


class TableConfig(BaseModel):
    """Configuration for a database table"""
    name: str = Field(..., description="Table name in database")
    description: Optional[str] = Field(None, description="Human-readable description of the table")
    discovery: bool = Field(True, description="Auto-discover DDL from database")
    notes: Optional[str] = Field(None, description="Important notes about this table")
    columns: Optional[Dict[str, ColumnConfig]] = Field(None, description="Column-level configurations")
    ddl_override: Optional[str] = Field(None, description="Manual DDL if discovery=false")
    include_in_training: bool = Field(True, description="Whether to include in Vanna training")


class ExampleQuery(BaseModel):
    """Example question-SQL pair for training"""
    question: str = Field(..., description="Natural language question")
    sql: str = Field(..., description="Corresponding SQL query")
    category: Optional[str] = Field(None, description="Query category (e.g., leaves, analytics)")
    description: Optional[str] = Field(None, description="Description of what this query does")


class DocumentationSection(BaseModel):
    """Documentation section for training"""
    topic: str = Field(..., description="Topic name")
    content: str = Field(..., description="Documentation content")


class RelationshipConfig(BaseModel):
    """Foreign key relationship configuration"""
    from_table: str = Field(..., description="Source table name")
    to_table: str = Field(..., description="Target table name")
    from_column: str = Field(..., description="Source column name")
    to_column: str = Field(..., description="Target column name")
    relationship_type: str = Field("many-to-one", description="Relationship type")
    description: Optional[str] = Field(None, description="Relationship description")


class SchemaMetadata(BaseModel):
    """Metadata about the schema configuration"""
    name: str = Field(..., description="Schema name (e.g., hrms, assets)")
    version: str = Field("1.0.0", description="Schema config version")
    description: Optional[str] = Field(None, description="Schema description")
    database_schema: str = Field("public", description="PostgreSQL schema name")


class SchemaTrainingConfig(BaseModel):
    """Root configuration model for schema training YAML"""
    schema_info: SchemaMetadata = Field(..., alias="schema", description="Schema metadata")
    tables: List[TableConfig] = Field(default_factory=list, description="Table configurations")
    examples: List[ExampleQuery] = Field(default_factory=list, description="Example queries")
    documentation: List[DocumentationSection] = Field(default_factory=list, description="Documentation sections")
    relationships: List[RelationshipConfig] = Field(default_factory=list, description="Table relationships")
    
    class Config:
        extra = "ignore"  # Ignore extra fields in YAML
        populate_by_name = True  # Allow using both 'schema' and 'schema_info'
