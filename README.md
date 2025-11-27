# Vanna SQL Service

A standalone microservice that converts natural language questions into SQL queries using Vanna AI. Supports automatic schema training, user-aware query generation, and role-based access control.

## 🚀 Features

- **Natural Language to SQL**: Convert questions like "Show my pending leaves" into SQL
- **Automatic Schema Training**: Train on database schema using YAML configuration
- **User-Aware Queries**: Automatic filtering based on user role (employee/manager/HR)
- **YAML-Based Configuration**: Maintain schema definitions, examples, and documentation in YAML
- **Vector Memory**: Uses Qdrant for storing trained examples and schema information
- **Production-Ready**: Connection pooling, health checks, error handling
- **Observable**: Optional Langfuse integration for tracing

## 📋 Prerequisites

- Docker & Docker Compose
- PostgreSQL database (HRMS or any schema)
- OpenAI API key
- Python 3.11+ (for local development)

## 🏗️ Architecture

```
┌─────────────────────┐
│   API Request       │
│ (Natural Language)  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Vanna SQL Service  │
│  (FastAPI)          │
│  Port: 8010         │
└──────────┬──────────┘
           │
    ┌──────┴───────┐
    │              │
    ▼              ▼
┌─────────┐   ┌─────────┐
│ Qdrant  │   │ OpenAI  │
│ Vector  │   │   LLM   │
│   DB    │   │ (GPT-4) │
└────┬────┘   └────┬────┘
     │             │
     └──────┬──────┘
            │
            ▼
   ┌────────────────┐
   │  Generated SQL │
   └────────┬───────┘
            │
            ▼
   ┌────────────────┐
   │   PostgreSQL   │
   │      HRMS      │
   └────────────────┘
```

## 🛠️ Quick Start

### Option 1: Docker Compose (Recommended)

1. **Clone and navigate to directory:**
   ```bash
   cd vanna-sql-service
   ```

2. **Create environment file:**
   ```bash
   cp .env.example .env
   # Edit .env and add your OPENAI_API_KEY and DATABASE_URL
   ```

3. **Start services:**
   ```bash
   docker-compose up -d
   ```

4. **Check health:**
   ```bash
   curl http://localhost:8010/health
   ```

5. **Access API docs:**
   Open http://localhost:8010/docs in your browser

### Option 2: Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start Qdrant (required):**
   ```bash
   docker run -d -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest
   ```

3. **Set environment variables:**
   ```bash
   # Windows PowerShell
   $env:DATABASE_URL="postgresql://postgres:password@localhost:5433/hrms"
   $env:OPENAI_API_KEY="sk-your-key-here"
   $env:QDRANT_URL="http://localhost:6333"
   ```

4. **Run the service:**
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
   ```

## 📝 Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | ✅ Yes | - | PostgreSQL connection string |
| `OPENAI_API_KEY` | ✅ Yes | - | OpenAI API key for LLM |
| `QDRANT_URL` | No | `http://localhost:6333` | Qdrant server URL |
| `QDRANT_COLLECTION` | No | `vanna_hrms` | Qdrant collection name |
| `OPENAI_MODEL` | No | `gpt-4` | OpenAI model to use |
| `SCHEMA_NAME` | No | `hrms` | Schema config file to load |
| `AUTO_TRAIN_ON_STARTUP` | No | `true` | Train on startup |
| `PORT` | No | `8010` | Service port |
| `LOG_LEVEL` | No | `INFO` | Logging level |

### Schema Configuration

Schema definitions are stored in `app/schemas/*.yaml`. The default HRMS schema is in `app/schemas/hrms.yaml`.

**Schema structure:**
```yaml
schema:
  name: hrms
  description: "HRMS database schema"

tables:
  - name: tr_leaves
    description: "Leave requests table"
    discovery: true  # Auto-discover DDL
    
examples:
  - question: "Show my pending leaves"
    sql: "SELECT * FROM tr_leaves WHERE employee_id = $CURRENT_USER_ID AND status = 'pending'"
    category: user_specific

documentation:
  - topic: "Schema Overview"
    content: "HRMS schema with leave management..."
```

## 🔌 API Endpoints

### Generate SQL

```bash
POST /api/generate-sql
```

**Request:**
```json
{
  "question": "Show my pending leave requests",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "employee",
  "execute": false
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "sql": "SELECT * FROM tr_leaves WHERE employee_id = '...' AND status = 'pending'",
    "explanation": "This query retrieves pending leave requests for the user"
  }
}
```

### Execute Query

```bash
POST /api/query
```

**Request:**
```json
{
  "question": "How many leaves did I take this year?",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "role": "employee",
  "execute": true
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "sql": "SELECT COUNT(*) FROM tr_leaves WHERE employee_id = '...' AND EXTRACT(YEAR FROM start_date) = EXTRACT(YEAR FROM CURRENT_DATE)",
    "results": [{"count": 12}],
    "execution_time_ms": 45
  }
}
```

### Train on Schema

```bash
POST /api/train-schema
```

Trains Vanna on the configured schema. This happens automatically on startup if `AUTO_TRAIN_ON_STARTUP=true`.

### Health Check

```bash
GET /health
```

Returns service health status and database connectivity.

## 🎯 Example Queries

### Employee Queries
- "Show my pending leave requests"
- "How many leaves did I take this year?"
- "What is my remaining annual leave balance?"

### Manager Queries
- "Show leave requests I need to approve"
- "List my team's leaves this month"
- "How many pending approvals do I have?"

### HR Queries
- "Show all pending leaves across the organization"
- "How many leaves were taken in Engineering this month?"
- "List all employees on leave today"

## 🔐 User-Aware Filtering

The service automatically applies user context filtering:

- **Employee Role**: Filters by `employee_id = user_id`
- **Manager Role**: Filters by `manager_id = user_id` (shows direct reports)
- **HR Role**: No filtering (can see all data)

## 🧪 Testing

### Test SQL Generation

```bash
curl -X POST http://localhost:8010/api/generate-sql \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show my pending leaves",
    "user_id": "your-uuid-here",
    "role": "employee",
    "execute": false
  }'
```

### Test Query Execution

```bash
curl -X POST http://localhost:8010/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many employees are there?",
    "execute": true
  }'
```

### Check Training Status

```bash
curl http://localhost:8010/api/trained-tables
```

## 🐳 Docker Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f vanna-sql-service

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Remove volumes (clean start)
docker-compose down -v
```

## 📁 Project Structure

```
vanna-sql-service/
├── app/
│   ├── api/              # API routes
│   │   ├── __init__.py
│   │   └── routes.py
│   ├── config/           # Configuration
│   │   ├── __init__.py
│   │   └── settings.py
│   ├── database/         # Database manager
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── models/           # Pydantic models
│   │   ├── __init__.py
│   │   └── schemas.py
│   ├── schemas/          # YAML schema configs
│   │   ├── __init__.py
│   │   ├── models.py     # Pydantic validation models
│   │   ├── loader.py     # YAML loader
│   │   └── hrms.yaml     # HRMS schema config
│   ├── services/         # Business logic
│   │   ├── __init__.py
│   │   └── vanna_service.py
│   ├── __init__.py
│   ├── client.py         # Client wrapper
│   └── main.py           # FastAPI app
├── .env.example          # Environment template
├── docker-compose.yml    # Docker Compose config
├── Dockerfile            # Container image
├── README.md             # This file
└── requirements.txt      # Python dependencies
```

## 🔧 Troubleshooting

### Issue: "Qdrant connection failed"

**Solution:** Ensure Qdrant is running:
```bash
docker-compose ps qdrant
# Should show "Up" status
```

### Issue: "OpenAI API error"

**Solution:** Check your API key is valid:
```bash
# Test key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

### Issue: "Database connection failed"

**Solution:** Verify database is accessible from container:
```bash
# If using host.docker.internal, ensure Docker Desktop is running
# Or update DATABASE_URL to use actual host IP
```

### Issue: "No training data"

**Solution:** Re-train the schema:
```bash
curl -X POST http://localhost:8010/api/train-schema
```

## 🔗 Integration with Leave Agent

The leave agent can query this service using the provided `vanna_client.py`:

```python
from vanna_client import VannaSQLClient

client = VannaSQLClient(base_url="http://localhost:8010")

# Generate and execute query
result = await client.query(
    question="Show my pending leaves",
    user_id="user-uuid",
    role="employee"
)

print(result["data"]["results"])
```

## 📊 Monitoring

### Health Endpoint

```bash
curl http://localhost:8010/health
```

Returns:
```json
{
  "status": "healthy",
  "service": "vanna-sql-service",
  "version": "2.0.0",
  "database": "connected",
  "qdrant": "connected"
}
```

### Logs

```bash
# Docker Compose
docker-compose logs -f vanna-sql-service

# Check last 100 lines
docker-compose logs --tail=100 vanna-sql-service
```

## 🚀 Production Deployment

### Considerations

1. **Security:**
   - Use secrets management for API keys
   - Enable authentication on Qdrant
   - Restrict CORS origins
   - Use HTTPS/TLS

2. **Scalability:**
   - Increase connection pool sizes
   - Deploy multiple service instances
   - Use managed Qdrant (Qdrant Cloud)

3. **Monitoring:**
   - Enable Langfuse integration
   - Add Prometheus metrics
   - Set up alerts for errors

4. **Performance:**
   - Cache frequent queries
   - Optimize schema training
   - Use read replicas for database

### Example Production docker-compose.yml

```yaml
services:
  vanna-sql-service:
    image: your-registry/vanna-sql-service:latest
    environment:
      - DATABASE_URL=${DATABASE_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - QDRANT_URL=https://your-qdrant.cloud:6333
      - QDRANT_API_KEY=${QDRANT_API_KEY}
      - CORS_ORIGINS=https://yourdomain.com
      - LOG_LEVEL=WARNING
      - LANGFUSE_PUBLIC_KEY=${LANGFUSE_PUBLIC_KEY}
      - LANGFUSE_SECRET_KEY=${LANGFUSE_SECRET_KEY}
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '1'
          memory: 1G
    restart: always
```

## 📚 Additional Resources

- [Vanna AI Documentation](https://vanna.ai/docs)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)

## 🤝 Contributing

This is a standalone service that can be extended with:
- Support for other databases (MySQL, SQL Server)
- Additional schema configurations
- Custom prompt templates
- Advanced caching strategies

## 📄 License

MIT License - feel free to use in your projects!

## 🆘 Support

For issues or questions:
1. Check the troubleshooting section above
2. Review logs: `docker-compose logs -f`
3. Verify environment variables in `.env`
4. Test database connectivity
5. Ensure Qdrant is running and accessible

## 🎉 Success!

Once running, you should see:
```
✅ Service ready!
📡 Listening on http://0.0.0.0:8010
```

Visit http://localhost:8010/docs to explore the API!
