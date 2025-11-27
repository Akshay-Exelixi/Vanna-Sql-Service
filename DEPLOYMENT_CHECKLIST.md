# Vanna SQL Service - Deployment Checklist

## ✅ Pre-Deployment Verification

### 1. File Structure
```
vanna-sql-service/
├── ✅ app/                          # Application code (copied from source)
├── ✅ .env.example                  # Environment template
├── ✅ .gitignore                    # Git ignore rules
├── ✅ docker-compose.yml            # Container orchestration
├── ✅ Dockerfile                    # Container image
├── ✅ Makefile                      # Development commands
├── ✅ PROJECT_SUMMARY.md            # Project overview
├── ✅ QUICKSTART.md                 # Quick start guide
├── ✅ README.md                     # Complete documentation
├── ✅ requirements.txt              # Python dependencies
└── ✅ start.ps1                     # Windows startup script
```

### 2. Required Environment Variables

Create `.env` file from `.env.example`:

```bash
# ✅ Required
DATABASE_URL=postgresql://user:pass@host:port/database
OPENAI_API_KEY=sk-your-actual-key-here

# ✅ Optional (defaults provided)
QDRANT_URL=http://qdrant:6333
QDRANT_COLLECTION=vanna_hrms
OPENAI_MODEL=gpt-4
SCHEMA_NAME=hrms
AUTO_TRAIN_ON_STARTUP=true
PORT=8010
HOST=0.0.0.0
LOG_LEVEL=INFO
CORS_ORIGINS=*
```

### 3. Docker Setup

- [ ] Docker Desktop installed and running
- [ ] Docker Compose available
- [ ] Ports 8010 and 6333 available
- [ ] Sufficient disk space (min 2GB)

### 4. Database Setup

- [ ] PostgreSQL database accessible
- [ ] Database URL correct format
- [ ] Database contains HRMS schema
- [ ] Network connectivity verified

### 5. API Keys

- [ ] OpenAI API key valid
- [ ] Sufficient OpenAI credits
- [ ] Langfuse keys (optional)
- [ ] Qdrant API key (if using Qdrant Cloud)

## 🚀 Deployment Steps

### Step 1: Initial Setup

```powershell
# Navigate to project directory
cd c:\Users\Akshay\Documents\Codes\ExelHRMS-BE-Agents\vanna-sql-service

# Create .env from template
cp .env.example .env

# Edit .env with your credentials
notepad .env
```

### Step 2: Verify Configuration

```powershell
# Check .env exists and has required variables
cat .env | Select-String -Pattern "DATABASE_URL|OPENAI_API_KEY"

# Test database connectivity (optional)
psql $env:DATABASE_URL -c "SELECT 1;"
```

### Step 3: Start Services

**Option A: Using PowerShell Script**
```powershell
.\start.ps1
```

**Option B: Using Docker Compose**
```powershell
docker-compose up -d
```

**Option C: Using Makefile**
```powershell
make start
```

### Step 4: Wait for Initialization

Services need 30-60 seconds to:
- Start containers
- Initialize database connections
- Connect to Qdrant
- Train Vanna on schema (24 examples)

```powershell
# Watch logs
docker-compose logs -f vanna-sql-service
```

Look for:
```
✅ Service ready!
📡 Listening on http://0.0.0.0:8010
```

### Step 5: Verify Health

```powershell
# Check service health
Invoke-RestMethod -Uri "http://localhost:8010/health"

# Expected response:
# {
#   "status": "healthy",
#   "service": "vanna-sql-service",
#   "version": "2.0.0",
#   "database": "connected",
#   "qdrant": "connected"
# }
```

### Step 6: Test API

```powershell
# Test SQL generation
$body = @{
    question = "Show all employees"
    execute = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8010/api/generate-sql" `
    -Method Post `
    -ContentType "application/json" `
    -Body $body
```

### Step 7: Verify Training

```powershell
# Check trained tables
Invoke-RestMethod -Uri "http://localhost:8010/api/trained-tables"

# Should return list of tables:
# {
#   "status": "success",
#   "data": {
#     "tables": ["tr_leaves", "employees", "roles", "leave_types", "departments"],
#     "examples_count": 24,
#     ...
#   }
# }
```

### Step 8: Access Documentation

Open in browser:
- **API Docs:** http://localhost:8010/docs
- **Health Check:** http://localhost:8010/health
- **Qdrant Dashboard:** http://localhost:6333/dashboard

## 🧪 Testing Checklist

### Basic Tests

- [ ] Health endpoint returns 200 OK
- [ ] API docs accessible
- [ ] Can generate SQL without execution
- [ ] Can execute simple query
- [ ] Training status shows tables

### User-Aware Tests

- [ ] Employee query filters by employee_id
- [ ] Manager query filters by manager_id
- [ ] HR query shows all data
- [ ] User context resolved correctly

### Integration Tests

- [ ] Leave agent can connect
- [ ] Natural language queries work
- [ ] Results returned correctly
- [ ] Errors handled gracefully

## 🔍 Health Check Commands

```powershell
# Service health
curl http://localhost:8010/health

# Container status
docker-compose ps

# Service logs
docker-compose logs -f vanna-sql-service

# Qdrant health
curl http://localhost:6333/healthz

# Database connection (from container)
docker-compose exec vanna-sql-service python -c "import asyncpg; import asyncio; asyncio.run(asyncpg.connect('$DATABASE_URL'))"
```

## ⚠️ Troubleshooting

### Issue: Service won't start

**Check:**
```powershell
# View logs
docker-compose logs vanna-sql-service

# Common issues:
# - Missing OPENAI_API_KEY
# - Invalid DATABASE_URL
# - Port 8010 already in use
# - Insufficient memory
```

**Fix:**
```powershell
# Stop and remove containers
docker-compose down

# Fix .env file
notepad .env

# Restart
docker-compose up -d
```

### Issue: Database connection failed

**Symptoms:**
- Service starts but health check fails
- Logs show database connection errors

**Fix:**
```powershell
# Update DATABASE_URL in .env
# For Docker host access:
# - Windows/Mac: host.docker.internal
# - Linux: actual host IP

# Example:
# DATABASE_URL=postgresql://postgres:password@host.docker.internal:5433/hrms
```

### Issue: Qdrant not starting

**Check:**
```powershell
docker-compose logs qdrant
docker-compose ps qdrant
```

**Fix:**
```powershell
# Remove Qdrant volume and restart
docker-compose down -v
docker-compose up -d
```

### Issue: Training failed

**Check:**
```powershell
# Look for training errors in logs
docker-compose logs vanna-sql-service | Select-String "training"
```

**Fix:**
```powershell
# Manually trigger training
curl -X POST http://localhost:8010/api/train-schema

# Or restart with fresh Qdrant
docker-compose down -v
docker-compose up -d
```

### Issue: OpenAI API errors

**Symptoms:**
- SQL generation fails
- "Invalid API key" errors

**Fix:**
```powershell
# Verify API key
$env:OPENAI_API_KEY = "sk-your-key"
curl https://api.openai.com/v1/models `
  -H "Authorization: Bearer $env:OPENAI_API_KEY"

# Update .env
notepad .env

# Restart
docker-compose restart
```

## 📊 Monitoring

### Container Status

```powershell
# All containers
docker-compose ps

# Resource usage
docker stats

# Specific container logs
docker-compose logs -f vanna-sql-service
docker-compose logs -f qdrant
```

### Service Metrics

```powershell
# Health check
curl http://localhost:8010/health

# Trained data
curl http://localhost:8010/api/trained-tables

# Database schema
curl http://localhost:8010/api/schema
```

### Log Monitoring

```powershell
# Follow logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Search logs
docker-compose logs | Select-String "ERROR"
docker-compose logs | Select-String "WARNING"
```

## 🎯 Success Indicators

✅ All containers running
✅ Health check returns healthy status
✅ API docs accessible
✅ Can generate SQL
✅ Can execute queries
✅ Training completed (24 examples)
✅ No errors in logs
✅ Database connected
✅ Qdrant connected

## 🔄 Maintenance

### Regular Tasks

**Daily:**
- [ ] Check service health
- [ ] Review error logs
- [ ] Monitor resource usage

**Weekly:**
- [ ] Review generated queries
- [ ] Update schema if needed
- [ ] Check OpenAI usage/costs

**Monthly:**
- [ ] Update dependencies
- [ ] Review and optimize examples
- [ ] Backup Qdrant data

### Update Procedure

```powershell
# 1. Pull latest code
git pull

# 2. Stop services
docker-compose down

# 3. Rebuild images
docker-compose build --no-cache

# 4. Start services
docker-compose up -d

# 5. Verify
curl http://localhost:8010/health
```

### Backup Procedure

```powershell
# Backup Qdrant data
docker-compose exec qdrant tar -czf /tmp/qdrant-backup.tar.gz /qdrant/storage

# Copy to host
docker cp $(docker-compose ps -q qdrant):/tmp/qdrant-backup.tar.gz ./qdrant-backup.tar.gz

# Backup configuration
cp .env .env.backup
cp app/schemas/hrms.yaml app/schemas/hrms.yaml.backup
```

## 📈 Scaling

### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  vanna-sql-service:
    deploy:
      replicas: 3
```

### Performance Tuning

```bash
# .env
DB_MIN_POOL_SIZE=5
DB_MAX_POOL_SIZE=20
MAX_QUERY_RESULTS=5000
QUERY_TIMEOUT=60
```

## 🚀 Production Deployment

### Checklist

- [ ] Use secrets management (not .env)
- [ ] Enable HTTPS/TLS
- [ ] Restrict CORS origins
- [ ] Use managed Qdrant service
- [ ] Set up monitoring/alerting
- [ ] Configure log aggregation
- [ ] Set resource limits
- [ ] Enable backup automation
- [ ] Use database read replicas
- [ ] Implement rate limiting

### Environment

```bash
# Production .env
CORS_ORIGINS=https://yourdomain.com
LOG_LEVEL=WARNING
QDRANT_URL=https://qdrant-prod.example.com:6333
QDRANT_API_KEY=prod-api-key
DATABASE_URL=postgresql://prod-user:secure-pass@prod-db:5432/hrms
```

## ✅ Final Verification

Before considering deployment complete:

1. **Service Running**
   - [ ] All containers up
   - [ ] No restart loops
   - [ ] Stable resource usage

2. **Functionality**
   - [ ] Health check passes
   - [ ] Can generate SQL
   - [ ] Can execute queries
   - [ ] Training successful

3. **Integration**
   - [ ] Leave agent connects
   - [ ] Sample queries work
   - [ ] User filtering works

4. **Documentation**
   - [ ] README reviewed
   - [ ] Quickstart tested
   - [ ] API docs verified

5. **Monitoring**
   - [ ] Logs clean
   - [ ] No errors
   - [ ] Performance acceptable

## 🎉 Deployment Complete!

Your Vanna SQL Service is now deployed and ready to use!

**Access Points:**
- API: http://localhost:8010
- Docs: http://localhost:8010/docs
- Health: http://localhost:8010/health

**Next Steps:**
1. Integrate with leave agent
2. Test with real queries
3. Monitor performance
4. Customize schema as needed

---

**Need Help?** Check [README.md](README.md) for detailed documentation!
