# Production Dockerfile for Trading System
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional production dependencies
RUN pip install --no-cache-dir \
    websockets \
    uvloop \
    supervisor

# Copy application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Default command (overridden by docker-compose)
CMD ["python", "ultra_simple_server.py"]

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8083/health')" || exit 1
