# Production Dockerfile for Trading System
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install additional production dependencies
RUN pip install --no-cache-dir \
    websockets \
    gunicorn \
    "brevo-python<2.0.0"

# Force rebuild - changing this ENV busts ALL subsequent layer caches
ENV BUILD_DATE=2026-02-21-1235

# Copy application code
COPY . .

# Create logs directory and initialize database
RUN mkdir -p /app/logs

# Set environment
ENV PYTHONUNBUFFERED=1

# Make start script executable
COPY start.sh .
RUN chmod +x start.sh

# Default command - use startup script
CMD ["./start.sh"]
