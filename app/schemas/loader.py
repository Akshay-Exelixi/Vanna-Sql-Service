"""
YAML schema configuration loader for Vanna training
"""
import yaml
import logging
from pathlib import Path
from typing import Optional, List

from .models import SchemaTrainingConfig

logger = logging.getLogger(__name__)


class SchemaConfigLoader:
    """Loader for YAML schema configuration files"""
    
    def __init__(self, schemas_dir: Optional[Path] = None):
        """
        Initialize the schema config loader.
        
        Args:
            schemas_dir: Directory containing YAML schema files.
                        Defaults to the directory containing this module.
        """
        self.schemas_dir = schemas_dir or Path(__file__).parent
    
    def load(self, schema_name: str) -> SchemaTrainingConfig:
        """
        Load and validate a schema YAML configuration file.
        
        Args:
            schema_name: Name of the schema (without .yaml extension)
            
        Returns:
            SchemaTrainingConfig: Validated schema configuration
            
        Raises:
            FileNotFoundError: If schema file doesn't exist
            ValueError: If YAML is invalid or fails validation
        """
        file_path = self.schemas_dir / f"{schema_name}.yaml"
        
        if not file_path.exists():
            # Also try .yml extension
            file_path = self.schemas_dir / f"{schema_name}.yml"
            if not file_path.exists():
                raise FileNotFoundError(
                    f"Schema config not found: {schema_name}.yaml in {self.schemas_dir}"
                )
        
        logger.info(f"📖 Loading schema config from: {file_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            if not data:
                raise ValueError(f"Empty schema config: {file_path}")
            
            # Validate using Pydantic model
            config = SchemaTrainingConfig(**data)
            
            logger.info(
                f"✅ Loaded schema '{config.schema_info.name}' v{config.schema_info.version}: "
                f"{len(config.tables)} tables, {len(config.examples)} examples"
            )
            
            return config
            
        except yaml.YAMLError as e:
            logger.error(f"❌ YAML parsing error in {file_path}: {e}")
            raise ValueError(f"Invalid YAML in schema config: {e}")
        except Exception as e:
            logger.error(f"❌ Failed to load schema config {schema_name}: {e}")
            raise
    
    def list_schemas(self) -> List[str]:
        """
        List available schema configuration files.
        
        Returns:
            List of schema names (without extension)
        """
        schemas = []
        for ext in ['*.yaml', '*.yml']:
            schemas.extend([f.stem for f in self.schemas_dir.glob(ext)])
        return sorted(set(schemas))
    
    def schema_exists(self, schema_name: str) -> bool:
        """
        Check if a schema configuration file exists.
        
        Args:
            schema_name: Name of the schema to check
            
        Returns:
            True if schema file exists
        """
        yaml_path = self.schemas_dir / f"{schema_name}.yaml"
        yml_path = self.schemas_dir / f"{schema_name}.yml"
        return yaml_path.exists() or yml_path.exists()
    
    def get_schema_path(self, schema_name: str) -> Optional[Path]:
        """
        Get the full path to a schema configuration file.
        
        Args:
            schema_name: Name of the schema
            
        Returns:
            Path to schema file, or None if not found
        """
        yaml_path = self.schemas_dir / f"{schema_name}.yaml"
        if yaml_path.exists():
            return yaml_path
        
        yml_path = self.schemas_dir / f"{schema_name}.yml"
        if yml_path.exists():
            return yml_path
        
        return None


# Global schema loader instance
schema_loader = SchemaConfigLoader()
