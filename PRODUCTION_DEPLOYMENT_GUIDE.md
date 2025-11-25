# Production Deployment Guide - Recorder Backend

This guide covers deploying the Recorder Backend Service for multiple users in a production environment.

## 🎯 Production Features

The recorder backend has been built with production in mind:

- ✅ **Multi-user support** - User isolation and authentication
- ✅ **Resource limits** - Per-user and global limits
- ✅ **Thread safety** - Proper locking for concurrent operations
- ✅ **Connection pooling** - Database connection management
- ✅ **Error recovery** - Automatic retry and cleanup
- ✅ **API authentication** - Secure API key authentication
- ✅ **Scalability** - Configurable limits and resource management

## 🔐 Security Configuration

### 1. Set API Key

**CRITICAL**: Set a strong API key before deploying:

```bash
# In .env file
RECORDER_API_KEY=your-very-secure-random-api-key-here
```

Generate a secure key:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. Environment Variables

Create `.env` file with production settings:

```bash
# Database
DB_PATH=/var/lib/just-trades/just_trades.db

# API Security
RECORDER_API_KEY=your-secure-api-key-here

# Resource Limits
MAX_RECORDINGS_PER_USER=10
MAX_CONCURRENT_RECORDINGS=100
POLL_INTERVAL_MIN=10
DB_POOL_SIZE=20

# Logging
LOG_LEVEL=INFO
```

## 🚀 Deployment Options

### Option 1: Gunicorn (Recommended for Production)

Install gunicorn:
```bash
pip install gunicorn
```

Run with gunicorn:
```bash
gunicorn -w 4 -b 0.0.0.0:8083 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level info \
  recorder_backend:app
```

**Gunicorn Configuration** (`gunicorn_config.py`):
```python
bind = "0.0.0.0:8083"
workers = 4
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 50
accesslog = "-"
errorlog = "-"
loglevel = "info"
```

Run with config:
```bash
gunicorn -c gunicorn_config.py recorder_backend:app
```

### Option 2: systemd Service

Create `/etc/systemd/system/recorder-backend.service`:

```ini
[Unit]
Description=Recorder Backend Service
After=network.target

[Service]
Type=notify
User=www-data
Group=www-data
WorkingDirectory=/opt/just-trades
Environment="PATH=/opt/just-trades/venv/bin"
EnvironmentFile=/opt/just-trades/.env
ExecStart=/opt/just-trades/venv/bin/gunicorn -c gunicorn_config.py recorder_backend:app
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable recorder-backend
sudo systemctl start recorder-backend
sudo systemctl status recorder-backend
```

### Option 3: Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY recorder_backend.py .

EXPOSE 8083

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8083", "recorder_backend:app"]
```

Build and run:
```bash
docker build -t recorder-backend .
docker run -d \
  -p 8083:8083 \
  -v $(pwd)/.env:/app/.env \
  -v $(pwd)/just_trades.db:/app/just_trades.db \
  --name recorder-backend \
  recorder-backend
```

## 📊 Monitoring

### Health Check

Monitor service health:
```bash
curl http://localhost:8083/health
```

Response:
```json
{
  "status": "healthy",
  "active_recordings": 5,
  "active_users": 3,
  "tradovate_available": true,
  "max_concurrent": 100,
  "max_per_user": 10
}
```

### Logs

View logs:
```bash
# systemd
sudo journalctl -u recorder-backend -f

# Docker
docker logs -f recorder-backend

# Direct
tail -f recorder_backend.log
```

## 🔌 API Usage (Production)

### Authentication

All API endpoints (except `/health`) require authentication:

```bash
# Set API key in header
curl -H "X-API-Key: your-api-key-here" \
     -H "X-User-ID: 123" \
     http://localhost:8083/api/recorders/status
```

### Start Recording

```bash
curl -X POST \
  -H "X-API-Key: your-api-key-here" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "poll_interval": 30}' \
  http://localhost:8083/api/recorders/start/1
```

### Stop Recording

```bash
curl -X POST \
  -H "X-API-Key: your-api-key-here" \
  -H "X-User-ID: 123" \
  http://localhost:8083/api/recorders/stop/1
```

### Get Positions

```bash
curl -H "X-API-Key: your-api-key-here" \
     -H "X-User-ID: 123" \
     http://localhost:8083/api/recorders/positions/1?limit=50
```

## 🛡️ Security Best Practices

1. **Use HTTPS** - Deploy behind nginx/HAProxy with SSL
2. **API Key Rotation** - Rotate keys regularly
3. **Rate Limiting** - Add nginx rate limiting
4. **Firewall** - Only expose necessary ports
5. **Database Security** - Encrypt database at rest
6. **Logging** - Don't log sensitive data (passwords, tokens)

### Nginx Reverse Proxy

Example nginx config:
```nginx
upstream recorder_backend {
    server 127.0.0.1:8083;
}

server {
    listen 443 ssl;
    server_name recorder-api.yourdomain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://recorder_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Rate limiting
        limit_req zone=api_limit burst=20 nodelay;
    }
}
```

## 📈 Scaling

### Horizontal Scaling

For high load, run multiple instances behind a load balancer:

1. Run multiple gunicorn instances on different ports
2. Use nginx/HAProxy as load balancer
3. Use shared database (PostgreSQL recommended for production)
4. Consider Redis for shared state (active recordings)

### Vertical Scaling

Increase limits in `.env`:
```bash
MAX_CONCURRENT_RECORDINGS=500
MAX_RECORDINGS_PER_USER=50
DB_POOL_SIZE=50
```

## 🔄 Database Migration

For production, consider migrating from SQLite to PostgreSQL:

1. Install PostgreSQL adapter: `pip install psycopg2-binary`
2. Update connection string in code
3. Use connection pooling (SQLAlchemy recommended)

## 🐛 Troubleshooting

### Service won't start
- Check logs: `tail -f recorder_backend.log`
- Verify API key is set
- Check database permissions
- Verify port is not in use: `lsof -i :8083`

### High memory usage
- Reduce `DB_POOL_SIZE`
- Reduce `MAX_CONCURRENT_RECORDINGS`
- Check for connection leaks

### Slow performance
- Increase `DB_POOL_SIZE`
- Use PostgreSQL instead of SQLite
- Add database indexes
- Monitor Tradovate API rate limits

## 📝 Next Steps

1. Set up monitoring (Prometheus, Grafana)
2. Add alerting for errors
3. Set up log aggregation (ELK stack)
4. Implement database backups
5. Add API rate limiting per user
6. Consider using Celery for background tasks

