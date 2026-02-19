# Railway Deployment Reference — Just Trades Platform

> **Production URL**: `https://justtrades.app`
> **Branch**: `main` (auto-deploys on push)
> **Database**: PostgreSQL (Railway managed)
> **Last verified**: Feb 18, 2026

---

## QUICK REFERENCE

```bash
# Deploy (auto-deploy from git push)
git push origin main

# Manual deploy (bypasses git, uploads code directly)
railway up

# View logs (live tail)
railway logs --tail

# Check env vars (FULL values, not truncated)
railway variables --kv

# Set env var
railway variables --set "KEY=value"

# Restart service
railway restart

# Open production URL
railway open
```

---

## PROCFILE (Service Definitions)

```
web: python ultra_simple_server.py
worker: python webhook_worker.py
position_listener: python position_websocket_listener.py
recorder: python recorder_service.py
```

| Service | What It Does | Critical? |
|---------|-------------|-----------|
| `web` | Flask server — webhooks, API, admin UI | **YES** — all traffic |
| `worker` | Webhook worker (legacy) | Secondary |
| `position_listener` | WebSocket position listener | Secondary |
| `recorder` | Recorder service (trading engine) | **YES** — trade execution |

---

## DEPLOYMENT METHODS

### 1. Auto-Deploy (Git Push) — PRIMARY

```bash
git add specific_file.py
git commit -m "Description of change"
git push origin main
```

Railway auto-deploys within ~60-90 seconds of push to `main`. Nixpacks auto-detects Python, installs requirements.

**WARNING**: Every `git push origin main` triggers a production deploy. Double-check your changes.

### 2. Manual Deploy (Railway CLI)

```bash
railway up
```

Uploads current directory directly. Bypasses git. Useful for emergency hotfixes, but **no git history**. Prefer git push.

### 3. Rollback

```bash
# Via Railway dashboard: click previous deployment → Redeploy
# Via git: reset to stable tag and force push
git reset --hard WORKING_FEB18_2026_DCA_SKIP_STABLE
git push -f origin main  # CAUTION: force push triggers auto-deploy
```

---

## ENVIRONMENT VARIABLES

### Critical Variables

| Variable | Length | What It Does |
|----------|--------|-------------|
| `DATABASE_URL` | ~100+ | PostgreSQL connection string (Railway auto-set) |
| `REDIS_URL` | ~50+ | Redis connection string (Railway auto-set) |
| `SECRET_KEY` | ~32+ | Flask session secret |
| `WHOP_API_KEY` | **73+** | Whop company API key (`biz_*` prefix) |
| `WHOP_WEBHOOK_SECRET` | **40+** | Whop webhook signature secret (`whsec_*` prefix) |
| `SMTP_SERVER` | varies | Email server for welcome emails |
| `SMTP_USERNAME` | varies | Email login |
| `SMTP_PASSWORD` | varies | Email password |

### CRITICAL: Truncation Bug

Railway's **table display truncates** long values. `WHOP_API_KEY` showed 42 chars instead of full 73. This caused all Whop API calls to return 401.

**ALWAYS verify with:**

```bash
railway variables --kv  # Shows FULL values, not truncated table
```

**When setting long values:**

```bash
railway variables --set "WHOP_API_KEY=biz_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

### PostgreSQL Specifics

Railway provides `DATABASE_URL` automatically. Format:

```
postgresql://user:password@host:port/database
```

The app detects PostgreSQL via `is_using_postgres()` and switches SQL placeholders accordingly (`%s` vs `?`).

---

## DATABASE

### PostgreSQL on Railway

- Auto-provisioned when you add the PostgreSQL plugin
- `DATABASE_URL` set automatically
- Backups: Railway handles automatic backups
- Migrations: Run via `/api/run-migrations` endpoint or on startup

### Schema Migrations

Migrations use idempotent `ALTER TABLE ... ADD COLUMN` with `try/except`:

```python
try:
    cursor.execute('ALTER TABLE recorders ADD COLUMN new_column TEXT DEFAULT \'value\'')
except:
    pass  # Column already exists
```

**PostgreSQL string defaults use single quotes**, SQLite uses double quotes:

```python
if is_postgres:
    cursor.execute("ALTER TABLE t ADD COLUMN x TEXT DEFAULT 'value'")
else:
    cursor.execute('ALTER TABLE t ADD COLUMN x TEXT DEFAULT "value"')
```

---

## MONITORING

### Health Check Endpoints

```bash
# Broker execution status (queue depth, worker count)
curl -s "https://justtrades.app/api/broker-execution/status"

# Recent failures
curl -s "https://justtrades.app/api/broker-execution/failures?limit=20"

# Recent webhook activity
curl -s "https://justtrades.app/api/webhook-activity?limit=10"

# Raw webhook payloads
curl -s "https://justtrades.app/api/raw-webhooks?limit=10"

# Max loss monitor
curl -s "https://justtrades.app/api/admin/max-loss-monitor/status"

# Run migrations manually
curl -s "https://justtrades.app/api/run-migrations"
```

### Railway CLI Monitoring

```bash
# Live logs
railway logs --tail

# Service status
railway status

# Check deployment history
railway deployments
```

---

## RECOVERY PROTOCOL

### Quick Recovery (Git Tags)

```bash
# Current stable
git reset --hard WORKING_FEB18_2026_DCA_SKIP_STABLE
git push -f origin main

# Fallback chain (newest to oldest)
git reset --hard WORKING_FEB18_2026_FULL_AUDIT_STABLE
git reset --hard WORKING_FEB17_2026_MULTI_BRACKET_STABLE
git reset --hard WORKING_FEB16_2026_WHOP_SYNC_STABLE
git reset --hard WORKING_FEB12_2026_SPEED_RESTORED_STABLE
git reset --hard WORKING_FEB7_2026_PRODUCTION_STABLE  # THE BLUEPRINT
```

### Via Railway Dashboard

1. Go to Railway dashboard → your project
2. Click "Deployments" tab
3. Find the last working deployment
4. Click "Redeploy"

This is faster than git if you just need to roll back one deploy.

---

## COMMON ISSUES

### 1. Deploy Succeeds But App Crashes

```bash
railway logs --tail  # Check for ImportError, SyntaxError, NameError
```

Common causes:
- Missing import statement
- Undefined variable (test with `python3 -c "import py_compile; py_compile.compile('file.py')"`)
- New dependency not in `requirements.txt`

### 2. Environment Variable Not Working

```bash
railway variables --kv  # Check FULL value (not truncated)
railway variables --set "KEY=full_value_here"
railway restart  # May need restart after var change
```

### 3. Database Migration Failed

```bash
curl -s "https://justtrades.app/api/run-migrations"
```

If that fails, check logs for SQL errors. Remember: PostgreSQL uses `%s`, not `?`.

### 4. WebSocket Disconnects

The `position_listener` service may disconnect. It auto-reconnects, but check:

```bash
railway logs --tail  # Look for "WebSocket reconnecting" messages
```

### 5. Slow Response Times

Normal: < 200ms webhook response. If > 500ms:
- Check if paper trades switched from daemon thread to synchronous (Bug #9)
- Check if signal tracking is synchronous instead of daemon thread
- Check database connection pool size (should be 200, not 100)

---

## DEPLOYMENT CHECKLIST

Before every deploy to production:

- [ ] Syntax check: `python3 -c "import py_compile; py_compile.compile('file.py', doraise=True)"`
- [ ] Only changed files related to the current task
- [ ] Did NOT touch sacred functions unless approved
- [ ] No hardcoded `?` in SQL (must use `%s` for PostgreSQL)
- [ ] No background threads changed to synchronous
- [ ] No pool sizes downgraded
- [ ] Commit message describes the ONE change made
- [ ] If touching trading engine: test with real signal first

---

## RAILWAY CLI REFERENCE

```bash
# Project management
railway link            # Link current dir to Railway project
railway status          # Show project/service status
railway open            # Open project in browser

# Deployments
railway up              # Deploy current directory
railway logs --tail     # Stream live logs
railway restart         # Restart all services
railway deployments     # List recent deployments

# Environment variables
railway variables              # List variables (TABLE — may truncate!)
railway variables --kv         # List variables (FULL values — use this!)
railway variables --set "K=V"  # Set a variable

# Database
railway connect postgres  # Connect to PostgreSQL shell
railway run psql          # Run psql with Railway credentials
```

---

*Source: Production deployment experience with Just Trades platform on Railway*
