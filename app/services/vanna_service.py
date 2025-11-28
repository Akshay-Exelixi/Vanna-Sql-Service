"""
Vanna AI service for SQL generation from natural language
Uses Vanna 2.0 Agent-based architecture with Qdrant vector database
"""
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
import time
import asyncpg

from vanna import Agent, ToolRegistry
from vanna.integrations.openai import OpenAILlmService
from vanna.integrations.qdrant import QdrantAgentMemory
from vanna.tools import RunSqlTool
from vanna.core.user.resolver import UserResolver
from vanna.core.user.request_context import RequestContext
from vanna.core.user.models import User

from ..config import settings
from ..database import db_manager
from .sql_validator import SQLSecurityValidator, ValidationResult

logger = logging.getLogger(__name__)


class DatabaseUserResolver(UserResolver):
    """User resolver that fetches user details from HRMS database"""
    
    # System user IDs that should not be looked up in database
    SYSTEM_USER_IDS = {'system', 'training_system', 'sql_generator', 'anonymous', ''}
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    def _is_valid_uuid(self, value: str) -> bool:
        """Check if a string is a valid UUID"""
        import re
        uuid_pattern = re.compile(
            r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
            re.IGNORECASE
        )
        return bool(uuid_pattern.match(value))
    
    async def resolve_user(self, request_context: RequestContext) -> User:
        """
        Resolve user from database using employee and role tables.
        
        Expected metadata:
        - user_id: Employee UUID or 'system'
        - role: Optional role override (if not provided, fetched from DB)
        """
        metadata = request_context.metadata or {}
        user_id = metadata.get('user_id', 'system')
        role_override = metadata.get('role')
        
        # Default user for system/anonymous requests or non-UUID user IDs
        if user_id in self.SYSTEM_USER_IDS or not self._is_valid_uuid(user_id):
            return User(
                id=user_id or 'system',
                username=user_id or 'system',
                email=f'{user_id or "system"}@local',
                metadata=metadata,
                group_memberships=['system', 'default']
            )
        
        try:
            async with self.db_pool.acquire() as conn:
                # Fetch employee with role from database
                employee = await conn.fetchrow("""
                    SELECT 
                        e.id,
                        e.first_name,
                        e.last_name,
                        e.email,
                        e.position,
                        e.status,
                        e.department_id,
                        e.manager_id,
                        r.id as role_id,
                        r.name as role_name,
                        r.level as role_level,
                        d.name as department_name
                    FROM employees e
                    LEFT JOIN roles r ON e.role_id = r.id
                    LEFT JOIN departments d ON e.department_id = d.id
                    WHERE e.id = $1::uuid
                """, user_id)
                
                if employee:
                    # Determine group memberships based on role
                    role_name = role_override or employee['role_name'] or 'employee'
                    role_level = employee['role_level'] or 0
                    
                    # Build group memberships based on role level
                    group_memberships = ['default', 'employee']
                    if role_level >= 1:
                        group_memberships.append('staff')
                    if role_level >= 2:
                        group_memberships.append('supervisor')
                    if role_level >= 3:
                        group_memberships.append('manager')
                    if role_level >= 4:
                        group_memberships.append('hr')
                    if role_level >= 5:
                        group_memberships.append('admin')
                    
                    # Add role name to groups
                    group_memberships.append(role_name.lower())
                    
                    # Fetch team members if user is a manager (has direct reports)
                    team_member_ids = []
                    if role_level >= 3:  # Manager level or above
                        team_members = await conn.fetch("""
                            SELECT id FROM employees 
                            WHERE manager_id = $1::uuid AND status = 'active'
                        """, user_id)
                        team_member_ids = [str(tm['id']) for tm in team_members]
                    
                    # Fetch all employees in same department if HR or Admin
                    department_member_ids = []
                    if role_level >= 4 and employee['department_id']:  # HR level or above
                        dept_members = await conn.fetch("""
                            SELECT id FROM employees 
                            WHERE department_id = $1 AND status = 'active'
                        """, employee['department_id'])
                        department_member_ids = [str(dm['id']) for dm in dept_members]
                    
                    return User(
                        id=str(employee['id']),
                        username=f"{employee['first_name']} {employee['last_name']}",
                        email=employee['email'] or f"{user_id}@local",
                        metadata={
                            **metadata,
                            'employee_id': str(employee['id']),
                            'department_id': str(employee['department_id']) if employee['department_id'] else None,
                            'department_name': employee['department_name'],
                            'manager_id': str(employee['manager_id']) if employee['manager_id'] else None,
                            'role_id': employee['role_id'],
                            'role_name': role_name,
                            'role_level': role_level,
                            'position': employee['position'],
                            'status': employee['status'],
                            'team_member_ids': team_member_ids,  # Direct reports (for managers)
                            'department_member_ids': department_member_ids,  # Department members (for HR)
                            'is_manager': len(team_member_ids) > 0,
                            'is_hr': role_level >= 4
                        },
                        group_memberships=list(set(group_memberships))
                    )
                else:
                    logger.warning(f"Employee not found for user_id: {user_id}")
        
        except Exception as e:
            logger.error(f"Error resolving user from database: {e}")
        
        # Fallback: return basic user with provided role
        return User(
            id=user_id,
            username=user_id,
            email=f"{user_id}@local",
            metadata=metadata,
            group_memberships=['default', role_override or 'employee']
        )


class PostgresSQLRunner:
    """Custom SQL Runner for PostgreSQL integration with Vanna 2.0"""
    
    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize connection pool"""
        if not self.pool:
            self.pool = await asyncpg.create_pool(self.connection_string)
    
    async def run_sql(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL and return results"""
        if not self.pool:
            await self.initialize()
        
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [dict(row) for row in rows]
    
    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()


class VannaSQLService:
    """Service for SQL generation using Vanna 2.0 Agent-based architecture"""
    
    def __init__(self):
        self.agent: Optional[Agent] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.sql_runner: Optional[PostgresSQLRunner] = None
        self.memory: Optional[QdrantAgentMemory] = None
        self.user_resolver = None  # Store user resolver for training
        self.initialized = False
        self.trained_tables = set()
        self.security_validator = SQLSecurityValidator(settings)  # SQL security validator
    
    async def initialize(self):
        """Initialize Vanna 2.0 Agent with Qdrant memory and OpenAI LLM"""
        try:
            logger.info("🤖 Initializing Vanna 2.0 Agent...")
            
            # Check if OpenAI API key is set
            if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY == "":
                raise ValueError("OPENAI_API_KEY is not set. Please configure it in environment variables.")
            
            logger.info(f"Using OpenAI model: {settings.OPENAI_MODEL}")
            
            # Initialize OpenAI LLM Service
            llm_service = OpenAILlmService(
                api_key=settings.OPENAI_API_KEY,
                model=settings.OPENAI_MODEL
            )
            
            # Initialize Qdrant Agent Memory
            self.memory = QdrantAgentMemory(
                url=settings.QDRANT_URL,
                collection_name=settings.QDRANT_COLLECTION,
                api_key=settings.QDRANT_API_KEY
            )
            
            # Initialize PostgreSQL SQL Runner
            self.sql_runner = PostgresSQLRunner(settings.DATABASE_URL)
            await self.sql_runner.initialize()
            
            # Initialize Tool Registry
            self.tool_registry = ToolRegistry()
            
            # Register RunSqlTool with our PostgreSQL runner
            sql_tool = RunSqlTool(sql_runner=self.sql_runner)
            # access_groups defines which user groups can access this tool (empty list = all users)
            self.tool_registry.register_local_tool(sql_tool, access_groups=[])
            
            # Create database-backed user resolver (fetches from employees and roles tables)
            self.user_resolver = DatabaseUserResolver(self.sql_runner.pool)
            
            # Create Agent with correct parameters
            self.agent = Agent(
                llm_service=llm_service,
                tool_registry=self.tool_registry,
                user_resolver=self.user_resolver,
                agent_memory=self.memory
            )
            
            logger.info("✅ Vanna 2.0 Agent initialized successfully")
            self.initialized = True
            
            # Train with schema from YAML config (replaces hardcoded training)
            await self.train_on_schema_config(settings.SCHEMA_NAME)
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Vanna Agent: {e}")
            raise
    
    async def train_on_schema_config(
        self,
        schema_name: str = "hrms"
    ) -> Dict[str, Any]:
        """
        Train Vanna Agent using YAML schema configuration with database introspection.
        
        This hybrid approach:
        1. Loads schema config from YAML file (tables, examples, documentation)
        2. Auto-discovers DDL from database for tables with discovery=true
        3. Uses manual DDL for tables with discovery=false
        4. Trains on example queries from YAML
        5. Trains on documentation from YAML
        
        Args:
            schema_name: Name of schema config file (without .yaml extension)
            
        Returns:
            Dict with training results
        """
        try:
            logger.info(f"📚 Training Vanna Agent on schema config: {schema_name}")
            
            # Import required classes
            from vanna.core.tool.models import ToolContext
            from ..schemas import SchemaConfigLoader
            import uuid
            
            # Load YAML configuration
            loader = SchemaConfigLoader()
            
            if not loader.schema_exists(schema_name):
                logger.warning(f"Schema config '{schema_name}' not found. Available: {loader.list_schemas()}")
                return {
                    "success": False,
                    "error": f"Schema config '{schema_name}' not found",
                    "available_schemas": loader.list_schemas()
                }
            
            config = loader.load(schema_name)
            logger.info(f"📖 Loaded schema config: {config.schema_info.name} v{config.schema_info.version}")
            
            # Create context for training
            request_context = RequestContext(
                metadata={"user_id": "training_system", "type": "schema_training"}
            )
            user = await self.user_resolver.resolve_user(request_context)
            
            trained_count = 0
            trained_tables = []
            trained_examples = []
            errors = []
            
            # 1. Train on tables (hybrid: YAML config + database introspection)
            for table_cfg in config.tables:
                if not table_cfg.include_in_training:
                    logger.debug(f"  ⏭️ Skipping table: {table_cfg.name} (include_in_training=false)")
                    continue
                    
                try:
                    # Get DDL from database or use override
                    if table_cfg.discovery:
                        ddl = await db_manager.get_table_ddl(table_cfg.name)
                        logger.debug(f"  📊 Auto-discovered DDL for: {table_cfg.name}")
                    else:
                        ddl = table_cfg.ddl_override or f"-- No DDL for {table_cfg.name}"
                        logger.debug(f"  📝 Using manual DDL for: {table_cfg.name}")
                    
                    # Enhance DDL with notes from YAML config
                    if table_cfg.notes:
                        ddl += f"\n-- Notes:\n-- {table_cfg.notes.replace(chr(10), chr(10) + '-- ')}"
                    
                    if table_cfg.description:
                        ddl = f"-- {table_cfg.description}\n{ddl}"
                    
                    # Save DDL to memory
                    tool_context = ToolContext(
                        user=user,
                        conversation_id=f"training_{uuid.uuid4().hex[:8]}",
                        request_id=f"req_{uuid.uuid4().hex[:8]}",
                        agent_memory=self.memory,
                        metadata={"type": "ddl", "table": table_cfg.name}
                    )
                    
                    await self.memory.save_text_memory(
                        content=ddl,
                        context=tool_context
                    )
                    trained_count += 1
                    trained_tables.append(table_cfg.name)
                    self.trained_tables.add(table_cfg.name)
                    logger.info(f"  ✓ Trained DDL: {table_cfg.name}")
                    
                except Exception as e:
                    error_msg = f"Failed to train table {table_cfg.name}: {e}"
                    logger.warning(f"  ✗ {error_msg}")
                    errors.append(error_msg)
            
            # 2. Train on example queries from YAML
            for example in config.examples:
                try:
                    content = f"Question: {example.question}\nSQL: {example.sql}"
                    
                    tool_context = ToolContext(
                        user=user,
                        conversation_id=f"training_{uuid.uuid4().hex[:8]}",
                        request_id=f"req_{uuid.uuid4().hex[:8]}",
                        agent_memory=self.memory,
                        metadata={
                            "type": "example",
                            "category": example.category or "general"
                        }
                    )
                    
                    await self.memory.save_text_memory(
                        content=content,
                        context=tool_context
                    )
                    trained_count += 1
                    trained_examples.append(example.question)
                    logger.debug(f"  ✓ Trained example: {example.question[:50]}...")
                    
                except Exception as e:
                    error_msg = f"Failed to train example '{example.question[:30]}...': {e}"
                    logger.warning(f"  ✗ {error_msg}")
                    errors.append(error_msg)
            
            # 3. Train on documentation from YAML
            for doc in config.documentation:
                try:
                    content = f"Topic: {doc.topic}\n\n{doc.content}"
                    
                    tool_context = ToolContext(
                        user=user,
                        conversation_id=f"training_{uuid.uuid4().hex[:8]}",
                        request_id=f"req_{uuid.uuid4().hex[:8]}",
                        agent_memory=self.memory,
                        metadata={"type": "documentation", "topic": doc.topic}
                    )
                    
                    await self.memory.save_text_memory(
                        content=content,
                        context=tool_context
                    )
                    trained_count += 1
                    logger.debug(f"  ✓ Trained doc: {doc.topic}")
                    
                except Exception as e:
                    error_msg = f"Failed to train doc '{doc.topic}': {e}"
                    logger.warning(f"  ✗ {error_msg}")
                    errors.append(error_msg)
            
            # 4. Train on relationships as documentation
            if config.relationships:
                relationships_doc = "Database Relationships:\n"
                for rel in config.relationships:
                    relationships_doc += f"\n- {rel.from_table}.{rel.from_column} → {rel.to_table}.{rel.to_column}"
                    if rel.description:
                        relationships_doc += f" ({rel.description})"
                
                try:
                    tool_context = ToolContext(
                        user=user,
                        conversation_id=f"training_{uuid.uuid4().hex[:8]}",
                        request_id=f"req_{uuid.uuid4().hex[:8]}",
                        agent_memory=self.memory,
                        metadata={"type": "documentation", "topic": "relationships"}
                    )
                    
                    await self.memory.save_text_memory(
                        content=relationships_doc,
                        context=tool_context
                    )
                    trained_count += 1
                    logger.debug(f"  ✓ Trained relationships ({len(config.relationships)} relations)")
                except Exception as e:
                    logger.warning(f"  ✗ Failed to train relationships: {e}")
            
            logger.info(
                f"✅ Schema training complete: {len(trained_tables)} tables, "
                f"{len(trained_examples)} examples, {trained_count} total items"
            )
            
            return {
                "success": True,
                "schema_name": config.schema_info.name,
                "schema_version": config.schema_info.version,
                "trained_count": trained_count,
                "tables_trained": trained_tables,
                "examples_trained": len(trained_examples),
                "errors": errors if errors else None
            }
            
        except FileNotFoundError as e:
            logger.error(f"❌ Schema config file not found: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"❌ Schema training failed: {e}")
            return {"success": False, "error": str(e)}

    async def train_on_database_schema(
        self, 
        tables: Optional[List[str]] = None,
        schema_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Train Vanna Agent on database schema using memory
        
        In Vanna 2.0, we need to create proper ToolContext with all required fields.
        
        Args:
            tables: Specific tables to train on (if None, trains on all)
            schema_name: Context name for training (e.g., 'leaves', 'assets')
        """
        try:
            logger.info(f"📚 Training Vanna Agent on database schema...")
            
            # Get tables to train on
            if not tables:
                tables = await db_manager.get_all_tables()
            
            trained = []
            sample_questions = []
            
            # Import required classes for ToolContext
            from vanna.core.tool.models import ToolContext
            from vanna.core.user.request_context import RequestContext
            import uuid
            
            for table_name in tables:
                try:
                    # Get DDL
                    ddl = await db_manager.get_table_ddl(table_name)
                    
                    # Create a proper ToolContext with all required fields
                    # We need: user, conversation_id, request_id, agent_memory
                    request_context = RequestContext(
                        metadata={
                            "user_id": "training_system",
                            "type": "ddl",
                            "table": table_name,
                            "schema": schema_name or "default"
                        }
                    )
                    
                    # Resolve user using our resolver
                    user = await self.user_resolver.resolve_user(request_context)
                    
                    # Create ToolContext with all required fields
                    context = ToolContext(
                        user=user,
                        conversation_id=f"training_{uuid.uuid4().hex[:8]}",
                        request_id=f"req_{uuid.uuid4().hex[:8]}",
                        agent_memory=self.memory,
                        metadata={
                            "type": "ddl",
                            "table": table_name,
                            "schema": schema_name or "default"
                        }
                    )
                    
                    # Store DDL in memory (async operation)
                    await self.memory.save_text_memory(
                        content=ddl,
                        context=context
                    )
                    
                    trained.append(table_name)
                    self.trained_tables.add(table_name)
                    
                    logger.info(f"  ✓ Trained on table: {table_name}")
                    
                    # Add sample questions for common tables
                    questions = self._generate_sample_questions(table_name, schema_name)
                    for question, sql in questions:
                        try:
                            # Create context for example
                            example_request_context = RequestContext(
                                metadata={
                                    "user_id": "training_system",
                                    "type": "example",
                                    "table": table_name,
                                    "question": question,
                                    "sql": sql
                                }
                            )
                            
                            example_user = await self.user_resolver.resolve_user(example_request_context)
                            
                            example_context = ToolContext(
                                user=example_user,
                                conversation_id=f"training_{uuid.uuid4().hex[:8]}",
                                request_id=f"req_{uuid.uuid4().hex[:8]}",
                                agent_memory=self.memory,
                                metadata={
                                    "type": "example",
                                    "table": table_name,
                                    "question": question,
                                    "sql": sql
                                }
                            )
                            
                            await self.memory.save_text_memory(
                                content=f"Question: {question}\nSQL: {sql}",
                                context=example_context
                            )
                            sample_questions.append(question)
                        except Exception as e:
                            logger.warning(f"Failed to train question for {table_name}: {e}")
                    
                except Exception as e:
                    logger.warning(f"Failed to train on table {table_name}: {e}")
                    continue
            
            logger.info(f"✅ Training complete. Trained on {len(trained)} tables")
            
            return {
                "success": True,
                "tables_trained": trained,
                "sample_questions": sample_questions
            }
            
        except Exception as e:
            logger.error(f"❌ Training failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "tables_trained": []
            }
    
    async def generate_sql(
        self, 
        question: str,
        context: Optional[str] = None,
        role: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate SQL from natural language question using Vanna 2.0 Agent
        
        Args:
            question: Natural language question
            context: Additional context (e.g., 'leaves', 'assets')
            role: User role for RBAC filtering
            user_id: User's employee ID for personalized queries
        """
        if not self.initialized:
            return {
                "success": False,
                "error": "Vanna Agent not initialized"
            }
        
        try:
            start_time = time.time()
            
            logger.info(f"🔍 Generating SQL for: {question} (user: {user_id}, role: {role})")
            
            # Import required classes for ToolContext
            from vanna.core.user.request_context import RequestContext
            from vanna.core.tool.models import ToolContext
            import uuid
            
            # Create request context for user resolution with actual user_id
            request_context = RequestContext(
                metadata={
                    "user_id": user_id or "sql_generator",
                    "context": context, 
                    "role": role
                }
            )
            
            # Resolve user to get full context (team members, department, etc.)
            user = await self.user_resolver.resolve_user(request_context)
            
            # Create ToolContext for memory search
            tool_context = ToolContext(
                user=user,
                conversation_id=f"query_{uuid.uuid4().hex[:8]}",
                request_id=f"req_{uuid.uuid4().hex[:8]}",
                agent_memory=self.memory,
                metadata={"context": context, "role": role}
            )
            
            # Retrieve relevant context from memory with proper ToolContext
            relevant_context = await self.memory.search_text_memories(
                query=question,
                context=tool_context,
                limit=5
            )
            
            logger.info(f"📚 Retrieved {len(relevant_context)} context items from memory")
            
            # Build prompt with context - extract content from memory objects
            context_items = []
            for idx, item in enumerate(relevant_context):
                # Try to extract content from the memory search result
                content = None
                if hasattr(item, 'memory'):
                    memory = item.memory
                    if hasattr(memory, 'content'):
                        content = memory.content
                    elif hasattr(memory, 'text'):
                        content = memory.text
                elif hasattr(item, 'content'):
                    content = item.content
                elif hasattr(item, 'text'):
                    content = item.text
                
                if content:
                    context_items.append(f"Reference {idx+1}:\n{content}")
                    logger.debug(f"Context item {idx+1}: {content[:100]}...")
                else:
                    logger.warning(f"Could not extract content from item {idx+1}: {type(item).__name__}")
            
            context_str = "\n\n".join(context_items)
            
            logger.info(f"Context string length: {len(context_str)} chars")
            logger.debug(f"Context preview: {context_str[:500]}..." if len(context_str) > 500 else f"Context: {context_str}")
            
            # Build user context information for personalized queries
            user_context_info = ""
            if user and user.id not in self.user_resolver.SYSTEM_USER_IDS:
                user_info = user.metadata
                user_context_info = f"""
Current User Context:
- User ID (employee_id): {user.id}
- Role: {user_info.get('role_name', 'employee')} (Level: {user_info.get('role_level', 0)})
- Department: {user_info.get('department_name', 'Unknown')}
- Is Manager: {user_info.get('is_manager', False)}
- Team Members: {len(user_info.get('team_member_ids', []))} direct reports

When the question contains phrases like:
- "my leaves", "my pending requests" → Filter by employee_id = '{user.id}'::uuid
- "leaves I need to approve", "pending approvals" → Filter by e.manager_id = '{user.id}'::uuid AND status = 'pending'
- "my team's leaves" → Filter by e.manager_id = '{user.id}'::uuid
- "leaves I approved" → Filter by approved_by = '{user.id}'::uuid

Replace $CURRENT_USER_ID placeholder with '{user.id}' in generated SQL.
"""
            
            # Create prompt for SQL generation with user context
            prompt = f"""You are a SQL expert for an HRMS (Human Resource Management System) database. Generate a PostgreSQL query to answer the following question.

⚠️ CRITICAL TABLE NAMING RULES - READ FIRST ⚠️
The following table names DO NOT EXIST and must NEVER be used:
- ❌ leave_requests → ✅ Use 'tr_leaves' instead
- ❌ leaves → ✅ Use 'tr_leaves' instead
- ❌ leave_applications → ✅ Use 'tr_leaves' instead
- ❌ time_off → ✅ Use 'tr_leaves' instead
- ❌ pto_requests → ✅ Use 'tr_leaves' instead

CORRECT TABLE NAMES (use ONLY these):
- tr_leaves: Leave requests and approvals (THE ONLY table for leave data)
- employees: Employee master data
- roles: Role definitions  
- leave_types: Types of leaves (sick, vacation, etc.)
- departments: Organization departments
- permissions: Permission definitions
- tr_role_permissions: Role-to-permission mappings

The 'tr_' prefix indicates a TRANSACTION table.

⚠️ CRITICAL RULES FOR MULTIPLE SQL STATEMENTS ⚠️
If the question requires multiple queries (e.g., "show X and also Y"):
1. Each SQL statement MUST be completely self-contained and independent
2. DO NOT define a CTE (WITH clause) in one statement and reference it in another
3. Each statement must include its own WITH clause if it needs a CTE
4. Statements are executed separately - they cannot share CTEs or temporary tables

Example of WRONG approach:
```
WITH data AS (SELECT ...) SELECT ... FROM data;  -- Statement 1 defines CTE
SELECT ... FROM data;  -- Statement 2 FAILS - 'data' doesn't exist here!
```

Example of CORRECT approach:
```
WITH data AS (SELECT ...) SELECT ... FROM data;  -- Statement 1 with its own CTE
WITH data AS (SELECT ...) SELECT ... FROM data;  -- Statement 2 with its own CTE (duplicated)
```
{user_context_info}

Context (DDL, Examples, and Documentation):
{context_str}

Question: {question}

Generate ONLY the SQL query, no explanations. Use ONLY the exact table names listed above.
If the question is user-specific (contains "my", "I"), apply appropriate WHERE filters based on the current user context.
If generating multiple statements, ensure each is completely self-contained."""
            
            # Use agent to generate SQL - collect all UI components
            logger.info("🤖 Sending message to Vanna Agent...")
            response_text = ""
            component_count = 0
            async for component in self.agent.send_message(
                request_context=request_context,
                message=prompt
            ):
                component_count += 1
                component_type = type(component).__name__
                
                # Extract text from Vanna UiComponent
                extracted = None
                
                # Vanna returns UiComponent with simple_component attribute
                if hasattr(component, 'simple_component') and component.simple_component:
                    simple = component.simple_component
                    if hasattr(simple, 'text') and simple.text:
                        extracted = str(simple.text)
                        logger.debug(f"Component {component_count} (simple_component.text): {extracted[:100]}...")
                
                # Fallback: try direct text attributes
                if not extracted:
                    for attr in ['content', 'text', 'message', 'output', 'value']:
                        if hasattr(component, attr):
                            val = getattr(component, attr)
                            if val and isinstance(val, (str, int, float)):
                                extracted = str(val)
                                logger.debug(f"Component {component_count} ({attr}): {extracted[:100]}...")
                                break
                
                # Fallback: try model_dump
                if not extracted and hasattr(component, 'model_dump'):
                    data = component.model_dump()
                    # Check simple_component in dumped data
                    if 'simple_component' in data and data['simple_component']:
                        sc = data['simple_component']
                        if isinstance(sc, dict) and 'text' in sc:
                            extracted = str(sc['text'])
                            logger.debug(f"Component {component_count} (model_dump.simple_component.text): {extracted[:100]}...")
                
                if extracted:
                    response_text += extracted + "\n"
                else:
                    logger.debug(f"Component {component_count} ({component_type}): No text content")
            
            logger.info(f"📨 Received {component_count} components, total length: {len(response_text)} chars")
            logger.info(f"Raw response: {response_text}")
            
            # Check if response is empty
            if not response_text or not response_text.strip():
                error_msg = "Agent returned empty response"
                logger.error(f"❌ {error_msg}")
                logger.error(f"Prompt was: {prompt}")
                logger.error(f"Context items: {len(relevant_context)}")
                return {
                    "success": False,
                    "error": error_msg,
                    "sql": "",
                    "debug_info": {
                        "prompt_length": len(prompt),
                        "context_items": len(relevant_context),
                        "component_count": component_count
                    }
                }
            
            # Extract SQL from response
            sql = self._extract_sql_from_response(response_text)
            logger.info(f"📝 Extracted SQL length: {len(sql)} chars")
            logger.info(f"Extracted SQL: {sql}")
            
            execution_time = time.time() - start_time
            
            # Validate and sanitize SQL (basic validation)
            validation = self._validate_sql(sql)
            if not validation['valid']:
                logger.warning(f"❌ SQL validation failed: {validation['error']}")
                logger.warning(f"Raw response was: {response_text[:500]}")
                return {
                    "success": False,
                    "error": validation['error'],
                    "sql": sql,
                    "debug_info": {
                        "response_length": len(response_text),
                        "component_count": component_count,
                        "context_items": len(relevant_context)
                    }
                }
            
            # Security validation (role-based access, injection detection, placeholder replacement)
            user_metadata = user.metadata if user else {}
            security_result = self.security_validator.validate(
                sql=sql,
                user_id=user_id,
                role=user_metadata.get('role_name', role),
                user_metadata=user_metadata
            )
            
            # Check for security errors (hard failures)
            if not security_result.is_valid:
                logger.warning(f"❌ Security validation failed: {security_result.errors}")
                return {
                    "success": False,
                    "error": f"Security validation failed: {'; '.join(security_result.errors)}",
                    "sql": sql,
                    "metadata": {
                        "security_validated": False,
                        "role_level": security_result.role_level,
                        "validation_errors": security_result.errors
                    }
                }
            
            # Use the potentially modified SQL (with placeholders replaced)
            validated_sql = security_result.sql
            
            # Log any security warnings
            if security_result.warnings:
                logger.info(f"⚠️ Security warnings: {security_result.warnings}")
            
            # Log any modifications made
            if security_result.modifications:
                logger.info(f"🔧 SQL modifications: {security_result.modifications}")
            
            logger.info(f"✅ SQL generated and validated in {execution_time:.2f}s")
            
            return {
                "success": True,
                "sql": validated_sql,
                "execution_time": execution_time,
                "explanation": f"Generated SQL for: {question}",
                "metadata": {
                    "security_validated": True,
                    "role_level": security_result.role_level,
                    "validation_warnings": security_result.warnings,
                    "modifications": security_result.modifications
                }
            }
            
        except Exception as e:
            logger.error(f"❌ SQL generation failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from agent response"""
        # Remove markdown code blocks if present
        sql = response.strip()
        
        # Remove ```sql and ``` markers
        if sql.startswith('```'):
            lines = sql.split('\n')
            # Remove first line (```sql or ```)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            sql = '\n'.join(lines)
        
        return sql.strip()
    
    def _split_sql_statements(self, sql: str) -> List[str]:
        """
        Split SQL string into individual statements.
        Handles semicolons inside strings properly.
        Strips leading comments from each statement.
        """
        statements = []
        current_statement = ""
        in_string = False
        string_char = None
        
        i = 0
        while i < len(sql):
            char = sql[i]
            
            # Handle string boundaries
            if char in ("'", '"') and (i == 0 or sql[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    string_char = char
                elif char == string_char:
                    in_string = False
                    string_char = None
            
            # Split on semicolon if not in string
            if char == ';' and not in_string:
                stmt = current_statement.strip()
                if stmt:
                    # Check if statement has actual SQL (not just comments)
                    stripped = self._strip_sql_comments(stmt)
                    if stripped:
                        statements.append(stmt)  # Keep original with comments for context
                current_statement = ""
            else:
                current_statement += char
            
            i += 1
        
        # Don't forget the last statement (may not have trailing semicolon)
        stmt = current_statement.strip()
        if stmt:
            stripped = self._strip_sql_comments(stmt)
            if stripped:
                statements.append(stmt)
        
        return statements
    
    async def generate_and_execute_sql(
        self,
        question: str,
        context: Optional[str] = None,
        role: Optional[str] = None,
        user_id: Optional[str] = None,
        max_rows: Optional[int] = None
    ) -> Dict[str, Any]:
        """Generate SQL and execute it with user context. Supports multiple SQL statements."""
        
        # Generate SQL with user context
        result = await self.generate_sql(question, context, role, user_id)
        
        if not result['success']:
            return result
        
        sql = result['sql']
        
        # Split into multiple statements if present
        sql_statements = self._split_sql_statements(sql)
        
        logger.info(f"📋 SQL contains {len(sql_statements)} statement(s)")
        
        # If multiple statements, execute each separately
        if len(sql_statements) > 1:
            return await self._execute_multiple_statements(
                sql_statements=sql_statements,
                original_sql=sql,
                generation_time=result.get('execution_time', 0),
                max_rows=max_rows,
                metadata=result.get('metadata')
            )
        
        # Single statement execution (original logic)
        # Determine operation type
        operation_type = self._get_operation_type(sql)
        
        try:
            start_time = time.time()
            
            # Execute based on operation type
            if operation_type in ['SELECT']:
                # Read operation
                rows = await db_manager.execute_query(
                    sql, 
                    max_rows=max_rows or settings.MAX_QUERY_RESULTS
                )
                execution_time = time.time() - start_time
                
                return {
                    "success": True,
                    "sql": sql,
                    "results": rows,
                    "row_count": len(rows),
                    "execution_time": result['execution_time'] + execution_time,
                    "operation": "read",
                    "explanation": result.get('explanation'),
                    "metadata": result.get('metadata')
                }
                
            elif operation_type in ['INSERT', 'UPDATE', 'DELETE']:
                # Write operation
                write_result = await db_manager.execute_write_query(sql)
                execution_time = time.time() - start_time
                
                return {
                    "success": True,
                    "sql": sql,
                    "rows_affected": write_result['rows_affected'],
                    "returning": write_result.get('returning', []),
                    "execution_time": result['execution_time'] + execution_time,
                    "operation": "write",
                    "explanation": result.get('explanation'),
                    "metadata": result.get('metadata')
                }
            else:
                return {
                    "success": False,
                    "error": f"Unsupported operation type: {operation_type}",
                    "sql": sql
                }
                
        except Exception as e:
            logger.error(f"❌ SQL execution failed: {e}")
            return {
                "success": False,
                "sql": sql,
                "error": f"Execution error: {str(e)}"
            }
    
    async def _execute_multiple_statements(
        self,
        sql_statements: List[str],
        original_sql: str,
        generation_time: float,
        max_rows: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute multiple SQL statements and return combined results.
        
        Args:
            sql_statements: List of individual SQL statements
            original_sql: Original combined SQL string
            generation_time: Time taken to generate SQL
            max_rows: Maximum rows per query
            metadata: Security metadata from generation
            
        Returns:
            Combined results with query_results array
        """
        try:
            start_time = time.time()
            
            # Execute all statements
            query_results = await db_manager.execute_multiple_queries(
                sql_statements,
                max_rows=max_rows or settings.MAX_QUERY_RESULTS
            )
            
            execution_time = time.time() - start_time
            
            # Calculate totals
            total_rows = sum(qr.get('row_count', 0) for qr in query_results)
            successful_queries = sum(1 for qr in query_results if qr.get('success'))
            failed_queries = len(query_results) - successful_queries
            
            logger.info(
                f"✅ Executed {len(query_results)} queries: "
                f"{successful_queries} succeeded, {failed_queries} failed, "
                f"{total_rows} total rows"
            )
            
            return {
                "success": failed_queries == 0,
                "sql": original_sql,
                "query_count": len(query_results),
                "query_results": query_results,
                "total_row_count": total_rows,
                "successful_queries": successful_queries,
                "failed_queries": failed_queries,
                "execution_time": generation_time + execution_time,
                "operation": "multi_read",
                "explanation": f"Executed {len(query_results)} SQL statements",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error(f"❌ Multiple statement execution failed: {e}")
            return {
                "success": False,
                "sql": original_sql,
                "error": f"Execution error: {str(e)}",
                "metadata": metadata
            }
    
    def _validate_sql(self, sql: str) -> Dict[str, Any]:
        """Validate generated SQL"""
        if not sql or not sql.strip():
            return {"valid": False, "error": "Empty SQL generated"}
        
        # Check for dangerous operations (configurable)
        dangerous_keywords = ['DROP', 'TRUNCATE', 'ALTER']
        sql_upper = sql.upper()
        
        for keyword in dangerous_keywords:
            if keyword in sql_upper:
                # Check if it's in ALLOWED_OPERATIONS
                if keyword not in settings.ALLOWED_OPERATIONS:
                    return {
                        "valid": False,
                        "error": f"Dangerous operation '{keyword}' not allowed"
                    }
        
        # Check if operation is allowed
        operation = self._get_operation_type(sql)
        if operation not in settings.ALLOWED_OPERATIONS:
            return {
                "valid": False,
                "error": f"Operation '{operation}' not allowed"
            }
        
        return {"valid": True}
    
    def _strip_sql_comments(self, sql: str) -> str:
        """
        Strip SQL comments from the beginning of SQL statements.
        Handles both single-line (--) and multi-line (/* */) comments.
        """
        sql = sql.strip()
        
        while sql:
            # Skip single-line comments
            if sql.startswith('--'):
                newline_idx = sql.find('\n')
                if newline_idx == -1:
                    return ''  # Entire SQL is a comment
                sql = sql[newline_idx + 1:].strip()
            # Skip multi-line comments
            elif sql.startswith('/*'):
                end_idx = sql.find('*/')
                if end_idx == -1:
                    return ''  # Unclosed comment
                sql = sql[end_idx + 2:].strip()
            else:
                break
        
        return sql
    
    def _get_operation_type(self, sql: str) -> str:
        """Extract operation type from SQL, ignoring leading comments"""
        # Strip comments before checking operation type
        sql_clean = self._strip_sql_comments(sql).upper()
        
        if sql_clean.startswith('SELECT') or sql_clean.startswith('WITH'):
            return 'SELECT'
        elif sql_clean.startswith('INSERT'):
            return 'INSERT'
        elif sql_clean.startswith('UPDATE'):
            return 'UPDATE'
        elif sql_clean.startswith('DELETE'):
            return 'DELETE'
        elif sql_clean.startswith('DROP'):
            return 'DROP'
        elif sql_clean.startswith('ALTER'):
            return 'ALTER'
        elif sql_clean.startswith('TRUNCATE'):
            return 'TRUNCATE'
        else:
            return 'UNKNOWN'
    
    def _generate_sample_questions(
        self, 
        table_name: str, 
        schema_name: Optional[str]
    ) -> List[tuple]:
        """Generate sample questions for training"""
        
        # Common patterns for different table types
        questions = []
        
        # Leaves-related tables
        if 'leave' in table_name.lower():
            questions = [
                (f"Show all pending leave requests", 
                 f"SELECT * FROM {table_name} WHERE status = 'pending'"),
                (f"Count leave requests by status",
                 f"SELECT status, COUNT(*) as count FROM {table_name} GROUP BY status"),
                (f"Show approved leaves this month",
                 f"SELECT * FROM {table_name} WHERE status = 'approved' AND EXTRACT(MONTH FROM created_at) = EXTRACT(MONTH FROM CURRENT_DATE)"),
            ]
        
        # Assets-related tables
        elif 'asset' in table_name.lower():
            questions = [
                (f"Show all available assets",
                 f"SELECT * FROM {table_name} WHERE status = 'available'"),
                (f"Count assets by category",
                 f"SELECT category, COUNT(*) as count FROM {table_name} GROUP BY category"),
            ]
        
        # Documents-related tables
        elif 'document' in table_name.lower():
            questions = [
                (f"Show recent documents",
                 f"SELECT * FROM {table_name} ORDER BY created_at DESC LIMIT 10"),
                (f"Count documents by type",
                 f"SELECT document_type, COUNT(*) as count FROM {table_name} GROUP BY document_type"),
            ]
        
        # Generic questions for any table
        questions.extend([
            (f"Show all records from {table_name}",
             f"SELECT * FROM {table_name} LIMIT 100"),
            (f"Count total records in {table_name}",
             f"SELECT COUNT(*) as total FROM {table_name}"),
        ])
        
        return questions
    
    # Helper methods to parse DATABASE_URL
    def _extract_host(self, url: str) -> str:
        match = re.search(r'@([^:]+):', url)
        return match.group(1) if match else 'localhost'
    
    def _extract_port(self, url: str) -> int:
        match = re.search(r':(\d+)/', url)
        return int(match.group(1)) if match else 5432
    
    def _extract_dbname(self, url: str) -> str:
        match = re.search(r'/([^?]+)', url)
        return match.group(1) if match else 'postgres'
    
    def _extract_user(self, url: str) -> str:
        match = re.search(r'://([^:]+):', url)
        return match.group(1) if match else 'postgres'
    
    def _extract_password(self, url: str) -> str:
        match = re.search(r':([^@]+)@', url)
        return match.group(1) if match else ''


# Global service instance
vanna_service = VannaSQLService()
