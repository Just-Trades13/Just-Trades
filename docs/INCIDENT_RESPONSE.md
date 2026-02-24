# Incident Response Playbook — Just Trades Platform

> **Step-by-step procedures for production incidents.**
> **Last updated: Feb 24, 2026**

---

## Severity Levels

| Level | Definition | Response Time | Example |
|-------|-----------|---------------|---------|
| **SEV-1** | Total outage — NO trades executing | Immediate | NameError in sacred function, all workers dead |
| **SEV-2** | Degraded — Some trades failing | < 15 min | Token expired on one account, wrong position sizes |
| **SEV-3** | Single user — One account affected | < 1 hour | User's broker auth expired, trader disabled |

## SEV-1: Total Outage Response

**Symptoms:** No trades executing, all webhooks failing, service returning 500s.

**Step 1: Diagnose (< 2 minutes)**
```bash
curl -s "https://justtrades.app/health"
railway logs --tail
curl -s "https://justtrades.app/api/broker-execution/status"
```

**Step 2: Immediate Rollback (if code change caused it)**
```bash
git reset --hard WORKING_FEB24_2026_WS_SEMAPHORE_STABLE
git push -f origin main
# Wait ~90 seconds for Railway auto-deploy
```

**Step 3: Verify Recovery**
```bash
curl -s "https://justtrades.app/api/broker-execution/status"
# Confirm workers_alive = 10, queue_size = 0
```

**Step 4: Post-Incident**
- Check for missed signals during outage: `curl -s "https://justtrades.app/api/raw-webhooks?limit=50"`
- Check for orphaned positions: `curl -s "https://justtrades.app/api/broker-execution/failures?limit=50"`
- Position reconciliation daemon will auto-sync DB within 5 minutes (WS position monitor syncs in real-time)

## SEV-2: Degraded Performance

**Symptoms:** Some trades failing, high latency, wrong position sizes, TP/SL not placing.

**Common causes and fixes:**

| Symptom | Likely Cause | Diagnosis | Fix |
|---------|-------------|-----------|-----|
| Token expired errors | Token refresh daemon failed | `/api/accounts/auth-status` | User re-OAuth, or restart service |
| Wrong position sizes | Multiplier not applied, DCA mismatch | Check trader settings in DB | Verify multiplier, dca_enabled |
| TP/SL rejected | Price not on tick boundary | Check `broker-execution/failures` | Tick rounding bug (Rule 3) |
| High latency (>500ms) | Background thread changed to sync | Check logs for timing | Revert to stable tag |
| Queue growing | Workers stuck or dead | `/api/broker-execution/status` | `railway restart` |

## SEV-3: Single User Issue

**Symptoms:** One account not trading, one user can't log in, one trader getting wrong sizes.

**Diagnosis flow:**
1. Check trader enabled: `SELECT enabled FROM traders WHERE account_id = X`
2. Check account token: `/api/accounts/auth-status`
3. Check specific recorder: `/api/recorders/{id}/execution-status`
4. Check broker state: `/api/traders/{id}/broker-state`

## Common Failure Scenarios

**Scenario: Stale Records Polluting Position Detection**
```sql
SELECT id, recorder_id, ticker, side, status, entry_time
FROM recorded_trades WHERE status = 'open' ORDER BY entry_time;

UPDATE recorded_trades SET status = 'closed', exit_reason = 'manual_cleanup'
WHERE status = 'open' AND entry_time < NOW() - INTERVAL '24 hours';
```

**Scenario: Orphaned TP Orders on Broker**
```sql
-- Position reconciliation (runs automatically every 5 min) handles this
-- WS position monitor handles this in real-time
-- Manual trigger if needed:
-- curl -s "https://justtrades.app/api/run-migrations"
-- Then wait for next reconciliation cycle (5 min) or WS monitor (real-time)
```

**Scenario: Whop Users Not Getting Emails**
1. Check Whop sync: `curl -s "https://justtrades.app/api/admin/whop-sync-status"`
2. Check Brevo: Is `BREVO_API_KEY` set? Is brevo-python pinned <2.0.0?
3. Check stuck users: Look at `stuck_users` in sync status
4. Manual resend: Admin panel → Users → Resend activation

**Scenario: TradingView Prices Stale (10-15 min delay)**
1. Check: `curl -s "https://justtrades.app/api/tradingview/status"`
2. If `jwt_token_valid: false`: Session cookies expired
3. Fix: Get new cookies from browser, update DB (see Rule 27), redeploy

### Rollback Beyond Code

Sometimes the issue isn't just code — it's data state. After a code rollback:

1. **Stale DB records**: Check and clean `recorded_trades` with `status='open'` that shouldn't be
2. **Redis state**: `railway restart` clears in-memory state (signal tracking, dedup caches)
3. **Broker positions**: WS position monitor syncs in real-time; reconciliation safety net runs every 5 minutes
4. **Orphaned activation tokens**: Clean with `DELETE FROM activation_tokens WHERE expires_at < NOW()`

---

*Source: CLAUDE.md "INCIDENT RESPONSE PLAYBOOK" section*
