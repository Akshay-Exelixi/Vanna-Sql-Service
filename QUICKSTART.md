# Vanna SQL Service - Quick Start Guide

## 🚀 Get Started in 3 Minutes

### Step 1: Configure Environment (1 minute)

```bash
# Copy environment template
cp .env.example .env

# Edit .env and set these required values:
# - DATABASE_URL: Your PostgreSQL connection string
# - OPENAI_API_KEY: Your OpenAI API key
```

**Example .env:**
```bash
DATABASE_URL=postgresql://postgres:password@host.docker.internal:5433/hrms
OPENAI_API_KEY=sk-proj-your-actual-openai-api-key-here
```

### Step 2: Start Services (1 minute)

```bash
# Start Vanna SQL Service + Qdrant
docker-compose up -d

# Wait 30 seconds for initialization...
```

### Step 3: Test It! (1 minute)

```bash
# Check health
curl http://localhost:8010/health

# Test a query
curl -X POST http://localhost:8010/api/generate-sql \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show all pending leave requests",
    "execute": false
  }'
```

**🎉 That's it! You're running!**

## 📚 Next Steps

### View API Documentation
Open in browser: http://localhost:8010/docs

### Try Sample Queries

**Employee queries:**
```bash
curl -X POST http://localhost:8010/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many employees are there?",
    "execute": true
  }'
```

**Leave queries:**
```bash
curl -X POST http://localhost:8010/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Show pending leaves for last month",
    "execute": true
  }'
```

### Check Training Status

```bash
curl http://localhost:8010/api/trained-tables
```

## 🛠️ Useful Commands

```bash
# View logs
docker-compose logs -f vanna-sql-service

# Restart service
docker-compose restart

# Stop everything
docker-compose down

# Clean restart (removes data)
docker-compose down -v && docker-compose up -d
```

## 🐛 Troubleshooting

### Service won't start?

1. **Check logs:**
   ```bash
   docker-compose logs vanna-sql-service
   ```

2. **Common issues:**
   - Missing OPENAI_API_KEY → Add to .env
   - Database unreachable → Check DATABASE_URL
   - Port 8010 in use → Change PORT in docker-compose.yml

### Qdrant not starting?

```bash
# Check Qdrant status
docker-compose ps qdrant

# View Qdrant logs
docker-compose logs qdrant
```

### Database connection failed?

If using `localhost` in DATABASE_URL, change to:
- **Windows/Mac Docker Desktop:** `host.docker.internal`
- **Linux:** Use actual host IP address

Example:
```bash
DATABASE_URL=postgresql://postgres:password@host.docker.internal:5433/hrms
```

## 📖 Learn More

- Full documentation: [README.md](README.md)
- API examples: http://localhost:8010/docs
- Schema configuration: `app/schemas/hrms.yaml`

## 💡 Tips

1. **Customize Schema:** Edit `app/schemas/hrms.yaml` to match your database
2. **Add Examples:** More examples = better SQL generation
3. **Monitor Logs:** Watch logs to see what SQL is being generated
4. **Test First:** Use `execute: false` to see SQL before running

## 🎯 Integration with Your App

Use the provided Python client:

```python
from vanna_client import VannaSQLClient

client = VannaSQLClient(base_url="http://localhost:8010")

result = await client.query(
    question="Show my pending leaves",
    user_id="user-uuid",
    role="employee"
)
```

## ✅ Success Indicators

You should see:
```
✅ Service ready!
📡 Listening on http://0.0.0.0:8010

📚 API Endpoints:
  POST /api/generate-sql  - Generate SQL from natural language
  POST /api/query         - Generate and execute SQL
  GET  /health            - Health check
  GET  /docs              - Interactive API documentation
```

## 🚨 Important Notes

- **First Run:** Training takes ~30-60 seconds
- **Training:** Happens automatically on startup
- **Port 8010:** Service port (change in docker-compose.yml if needed)
- **Port 6333:** Qdrant port (don't change unless necessary)

## 🔗 URLs

- **API Service:** http://localhost:8010
- **API Docs:** http://localhost:8010/docs
- **Health Check:** http://localhost:8010/health
- **Qdrant Dashboard:** http://localhost:6333/dashboard

---

**Need help?** Check the full [README.md](README.md) for detailed documentation!
