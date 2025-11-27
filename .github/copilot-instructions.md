# Vanna SQL Service - AI Agent Instructions

## Project Overview
Standalone FastAPI microservice that converts natural language to SQL using Vanna AI 2.0 Agent-based architecture. Connects to PostgreSQL databases with automatic schema training from YAML configs.

## Architecture & Data Flow

```
User Question → FastAPI → VannaSQLService (Agent) → OpenAI LLM + Qdrant Memory → SQL Generation → PostgreSQL
```

**Key Components:**
- `app/main.py`: FastAPI app with lifespan manager (startup/shutdown)
- `app/services/vanna_service.py`: Vanna 2.0 Agent wrapper with custom `DatabaseUserResolver` and `PostgresSQLRunner`
- `app/schemas/`: YAML-based schema configs for training (NOT database schemas - these are training configs)
- `app/database/manager.py`: asyncpg connection pool manager
- `app/api/routes.py`: API endpoints (`/api/generate-sql`, `/api/train-schema`, `/health`)

## Critical Patterns

### 1. Vanna 2.0 Agent Architecture
Uses new Agent-based approach (not legacy VannaBase):
```python
# Initialize with 4 components:
agent = Agent(
    llm_service=OpenAILlmService,      # GPT-4 for SQL generation
    agent_memory=QdrantAgentMemory,    # Vector storage for training examples
    tool_registry=ToolRegistry,        # RunSqlTool registered here
    user_resolver=DatabaseUserResolver # Custom: fetches from employees table
)
```

**User Resolution Flow:** Request context → `DatabaseUserResolver` → Queries `employees` + `roles` tables → Returns `User` with metadata (team_member_ids, department_member_ids) → Agent uses for personalized SQL generation.

### 2. YAML Schema Training System
`app/schemas/*.yaml` files define training data (NOT database DDL):
- **Hybrid approach**: `discovery: true` tables auto-fetch DDL from database; `discovery: false` use manual DDL from YAML
- **Structure**: `schema.name/version`, `tables[].columns`, `examples[]` (question-SQL pairs), `documentation[]`
- **Training trigger**: Auto on startup if `AUTO_TRAIN_ON_STARTUP=true`, or manual via `POST /api/train-schema`
- **Example**: `hrms.yaml` defines leave management schema with role-based query examples

### 3. Database Connection Management
- Uses `asyncpg` pool (NOT psycopg2 for async operations)
- Pool lifecycle managed in `app/main.py` lifespan context
- **Important**: PostgreSQL connection string must use `postgresql://` (not `postgres://`)
- Docker Compose uses `host.docker.internal` to reach host DB from container

### 4. Role-Based Query Generation
User context automatically filters queries:
- **Employee**: Only sees own data (`WHERE employee_id = $user_id`)
- **Manager**: Sees team data (`WHERE employee_id IN ($team_member_ids)`)
- **HR/Admin**: Full access (`role_level >= 4`)
- Implemented via `DatabaseUserResolver.resolve_user()` which populates `User.metadata` with access lists

## Development Workflows

### Local Development
```powershell
# Start Qdrant only (required dependency)
docker run -d -p 6333:6333 qdrant/qdrant:latest

# Set environment
$env:DATABASE_URL="postgresql://user:pass@localhost:5433/hrms"
$env:OPENAI_API_KEY="sk-..."

# Run locally
uvicorn app.main:app --reload --port 8010
```

### Docker Development
```powershell
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f vanna-sql-service

# Rebuild after code changes
docker-compose up -d --build
```

### Testing Endpoints
```powershell
# Health check
curl http://localhost:8010/health

# Generate SQL (no execution)
curl -X POST http://localhost:8010/api/generate-sql `
  -H "Content-Type: application/json" `
  -d '{"question": "Show pending leaves", "user_id": "uuid-here", "execute": false}'

# Train on schema
curl -X POST http://localhost:8010/api/train-schema `
  -d '{"schema_name": "hrms"}'
```

## Common Modifications

### Adding New Schema Training Config
1. Create `app/schemas/new_schema.yaml` following `hrms.yaml` structure
2. Define `schema.name`, `tables[]` with `discovery: true/false`
3. Add example queries in `examples[]` with role-specific WHERE clauses
4. Set `SCHEMA_NAME=new_schema` in `.env` or call `/api/train-schema` with `schema_name`

### Modifying SQL Generation Logic
Edit `app/services/vanna_service.py`:
- `generate_sql()`: Core generation logic with user context injection
- `DatabaseUserResolver.resolve_user()`: User metadata population from database
- Training methods: `train_on_schema_config()` loads YAML and trains Vanna memory

### Adding API Endpoints
1. Define Pydantic models in `app/models/schemas.py`
2. Add route handler in `app/api/routes.py` (use `@router.post()` decorator)
3. Call `vanna_service` methods for Vanna operations

## Important Conventions

- **Table Naming**: Transaction tables use `tr_` prefix (e.g., `tr_leaves` not `leaves`)
- **Date Calculations**: Leave duration = `(end_date - start_date + 1)` days
- **Write Operations**: Always use `RETURNING *` with INSERT/UPDATE to get affected rows
- **User IDs**: UUID type - cast with `::uuid` in SQL or use parameterized queries
- **Error Handling**: All async operations wrapped in try-except with logger.error()
- **Logging**: Use existing logger in each module (configured in main.py)

## Key Dependencies

- `vanna==2.0.1`: Vanna 2.0 Agent framework (must install directly to venv, not user site-packages)
- `qdrant-client>=1.16.0`: Vector database client (uses `query_points` method in 1.8.0+)
- `openai`: OpenAI SDK for LLM service
- `fastapi==0.115.5` + `uvicorn`: Web framework
- `asyncpg==0.30.0`: Async PostgreSQL driver (prefer over psycopg2)
- `pydantic-settings`: Environment variable management

**Installation Note**: Use `pip install --target=".venv/Lib/site-packages" vanna==2.0.1 --force-reinstall --no-deps --upgrade` to ensure vanna is installed correctly in the venv.

## Debugging Tips

- **Service won't start**: Check `docker-compose logs vanna-sql-service` for initialization errors
- **Training fails**: Verify YAML syntax in `app/schemas/*.yaml` and database connectivity
- **SQL generation errors**: Check Qdrant has trained examples (`curl http://localhost:6333/dashboard`)
- **User resolution fails**: Ensure `employees` and `roles` tables exist with expected schema
- **Query timeout**: Adjust `QUERY_TIMEOUT` in settings.py (default 30s)

## Files to Reference
- `app/services/vanna_service.py` (lines 1-300): Agent initialization, user resolution, training logic
- `app/schemas/hrms.yaml`: Complete YAML schema config example
- `README.md`: Full API documentation with example requests
- `docker-compose.yml`: Environment variables and service configuration
