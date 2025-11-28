FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/

# Create schemas directory if not exists
RUN mkdir -p ./app/schemas

# Expose port (configurable via PORT env var, default 2011)
EXPOSE 2011

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Health check (uses PORT env var)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:${PORT:-2011}/health || exit 1

# Run the application (PORT is set via environment variable)
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-2011} --log-level info
