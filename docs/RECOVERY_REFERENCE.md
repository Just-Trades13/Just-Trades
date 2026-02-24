# External Dependencies & Recovery Reference — Just Trades Platform

> **If the database, Railway project, or TradingView alerts were lost, this section has everything needed to rebuild.**
> **Last updated: Feb 24, 2026**

---

## TradingView Alert Configuration

Each active recorder needs a TradingView alert pointing to its webhook URL. If alerts are lost, recreate them using this reference.

**Webhook URL pattern:** `https://justtrades.app/webhook/{webhook_token}`

**Alert message template (paste into TradingView Alert Message field):**
```json
{
    "action": "{{strategy.order.action}}",
    "ticker": "{{ticker}}",
    "contracts": {{strategy.order.contracts}},
    "price": {{strategy.order.price}},
    "position": "{{strategy.market_position}}",
    "time": "{{timenow}}"
}
```

**Active alerts needed (one per recorder):**

| Recorder | Symbol | Webhook Token Source | Chart/Indicator |
|----------|--------|---------------------|-----------------|
| JADNQ V.2 (ID: 71) | NQ (E-mini Nasdaq) | `SELECT webhook_token FROM recorders WHERE id=71` | User's NQ strategy |
| JADMNQ V.2 (ID: 70) | MNQ (Micro Nasdaq) | `SELECT webhook_token FROM recorders WHERE id=70` | Same strategy, micro contract |
| JADVIX Medium Risk V.2 (ID: 67) | MNQ | `SELECT webhook_token FROM recorders WHERE id=67` | VIX-based DCA strategy |
| JADVIX HIGH RISK V.2 (ID: 68) | MNQ | `SELECT webhook_token FROM recorders WHERE id=68` | Aggressive VIX DCA |
| MGC-C1MIN (ID: 69) | MGC (Micro Gold) | `SELECT webhook_token FROM recorders WHERE id=69` | 1-minute gold strategy |

**TradingView alert settings:**
- Condition: Per strategy's Pine Script logic
- Frequency: "Once per bar close" (safest — avoids 15/3min rate limit)
- Expiration: Set to far future or "Open-ended" if available
- Webhook URL: `https://justtrades.app/webhook/{token}` (HTTPS only, ports 80/443)
- **Account requirement:** TradingView Plus or higher + 2FA enabled

**If alerts auto-disabled (silent):** TradingView disables alerts after 15 triggers in 3 minutes with NO notification. Monitor via `/api/webhook-activity` — if no signals during market hours, check TradingView alerts first.

---

## Railway Environment Variables (Complete Reference)

**CRITICAL — Production will not function without these:**

| Variable | Length | Source | What It Does |
|----------|--------|--------|-------------|
| `DATABASE_URL` | ~100+ | Railway auto-set | PostgreSQL connection string |
| `REDIS_URL` | ~50+ | Railway auto-set | Redis for caching, paper trades, signal dedup |
| `BREVO_API_KEY` | ~40+ | Brevo dashboard → SMTP & API → API Keys | Activation email sending (brevo-python <2.0.0) |
| `TRADOVATE_API_CID` | ~4-5 | Tradovate developer portal | Client ID (can be overridden per account in DB) |
| `TRADOVATE_API_SECRET` | ~36 | Tradovate developer portal | Client secret (can be overridden per account in DB) |

**HIGHLY RECOMMENDED:**

| Variable | Source | What It Does |
|----------|--------|-------------|
| `ADMIN_API_KEY` | Self-generated | API key for admin endpoints |
| `FLASK_SECRET_KEY` | Self-generated (64-char hex) | Flask session encryption. If missing, auto-generates on each deploy (logs out all users) |
| `WHOP_API_KEY` | Whop dashboard → API → Company API Key | **Must be full 73 chars** — Railway truncates in UI (Rule 21) |
| `WHOP_WEBHOOK_SECRET` | Whop dashboard → Webhooks → Signing Secret | **Must be full value** — verify with `railway variables --kv` |

**OPTIONAL (feature-specific):**

| Variable | Source | What It Does |
|----------|--------|-------------|
| `BREVO_SENDER_EMAIL` | Your domain | From address for emails (default: `noreply@justtrades.com`) |
| `PLATFORM_URL` | — | Base URL for activation links (default: `https://www.justtrades.app`) |
| `DISCORD_BOT_TOKEN` | Discord developer portal | Discord notifications (if enabled) |
| `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` | Generated via `web-push` | Web push notifications |
| `FINNHUB_API_KEY` | Finnhub.io | Stock market data for dashboard |
| `OAUTH_REDIRECT_DOMAIN` | — | Override OAuth callback domain (default: auto-detected) |

**Verification after setting:**
```bash
railway variables --kv  # ALWAYS use --kv to see full values (not truncated table)
```

---

## Whop Product ID Mapping

Hardcoded in `whop_integration.py` lines 42-46 (NOT an env var):

| Whop Product ID | Plan Slug | Plan Name | Price |
|----------------|-----------|-----------|-------|
| `prod_PLACEHOLDER_COPY` | `pro_copy_trader` | Pro Copy Trader | $100/mo |
| `prod_l3u1RLWEjMIS7` | `platform_basic` | Basic+ | $200/mo |
| `prod_3RCOfsuDNX4cs` | `platform_premium` | Premium+ | $500/mo |
| `prod_oKaNSNRKgxXS3` | `platform_elite` | Elite+ | $1000/mo |

**TODO:** Replace `prod_PLACEHOLDER_COPY` with real Whop product ID once created.

---

## Database Backup & Restore

**Export current configs (automated):**
```bash
curl -s "https://justtrades.app/api/admin/export-configs?api_key=YOUR_KEY" > config_backup_$(date +%Y%m%d).json
```

**Full database backup:**
```bash
railway connect postgres
\copy (SELECT * FROM recorders) TO '/tmp/recorders_backup.csv' CSV HEADER;
\copy (SELECT * FROM traders) TO '/tmp/traders_backup.csv' CSV HEADER;
\copy (SELECT * FROM users) TO '/tmp/users_backup.csv' CSV HEADER;
\copy (SELECT * FROM accounts) TO '/tmp/accounts_backup.csv' CSV HEADER;

# Or full pg_dump
pg_dump "$DATABASE_URL" > full_backup_$(date +%Y%m%d).sql
```

**Railway automatic backups:** Railway manages PostgreSQL backups automatically. Check Railway dashboard → Database → Backups for point-in-time recovery.

---

## TradingView Session Cookies (Rule 27)

Expire ~every 3 months. When prices on dashboard become stale (10-15 min delayed):

1. Open Chrome → tradingview.com → login to premium account
2. DevTools (F12) → Application → Cookies → `tradingview.com`
3. Copy `sessionid` and `sessionid_sign` values
4. Update database:
```sql
UPDATE accounts SET tradingview_session = '{"sessionid":"NEW_VALUE","sessionid_sign":"NEW_VALUE"}' WHERE id = 459;
```
5. Redeploy: `git push origin main` or `railway restart`
6. Verify: `curl -s "https://justtrades.app/api/tradingview/status"` → `jwt_token_valid: true`

---

## Complete Platform Recovery Checklist

If rebuilding from scratch:

1. **Deploy code** — `git clone` + `railway up` or connect Railway to GitHub repo
2. **Set env vars** — All CRITICAL + RECOMMENDED vars above via `railway variables --set`
3. **Run migrations** — `curl -s "https://justtrades.app/api/run-migrations"`
4. **Restore DB** — Import from backup or recreate recorders/traders from `docs/PRODUCTION_CONFIGS.md`
5. **Whop integration** — Set `WHOP_API_KEY` + `WHOP_WEBHOOK_SECRET`, verify at `/api/whop/status`
6. **Broker auth** — Users re-authenticate via OAuth (tokens can't be transferred)
7. **TradingView alerts** — Recreate per the table above with correct webhook tokens
8. **TradingView cookies** — Extract and insert per Rule 27
9. **Verify** — Run Daily Monitoring Checklist in `docs/MONITORING_ENDPOINTS.md`
10. **Test** — Send a test webhook per `docs/TESTING_PROCEDURES.md`

---

*Source: CLAUDE.md "EXTERNAL DEPENDENCIES & FULL RECOVERY REFERENCE" section*
