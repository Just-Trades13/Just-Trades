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
    supervisor \
    eventlet \
    gevent \
    gevent-websocket

# Copy application code - cache bust: v2
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Set environment
ENV PYTHONUNBUFFERED=1

# Default command - use eventlet for socketio
CMD ["python", "ultra_simple_server.py"]
