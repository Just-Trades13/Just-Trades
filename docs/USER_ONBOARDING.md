# User Onboarding Flow — Just Trades Platform

> **Complete lifecycle from purchase to first trade.**
> **Last updated: Feb 24, 2026**

---

## Step 1: Purchase (Whop)

User purchases subscription on Whop marketplace. Whop fires webhook to `/webhooks/whop`.

**What can fail:** Webhook 403'd if `/webhooks/` not in CSRF exempt list (Bug #12). Whop API key truncated in Railway (Bug #13).

## Step 2: Account Creation

`auto_create_user_from_whop(email, whop_user_id)` in `account_activation.py` (~line 357):
1. Check if user exists by email (idempotent)
2. If new: generate temp username (`whop_{8_random_chars}`), random password
3. Call `create_user()` → insert into `users` table
4. Auto-approve via `approve_user(user.id)`
5. Generate 72-hour activation token
6. Send activation email via Brevo

**What can fail:** brevo-python version mismatch (Bug #24 — must pin <2.0.0). Email failure does NOT break account creation (try/except).

## Step 3: Activation Email

Sent via Brevo API (`account_activation.py` ~line 239):
- Uses `brevo_python.TransactionalEmailsApi` (v1.x API)
- HTML template with dark theme and blue "ACTIVATE MY ACCOUNT" button
- Activation URL: `{PLATFORM_URL}/activate?token={token}`
- Token expires in 72 hours

**What can fail:** brevo-python v4 breaks imports (Rule 29). BREVO_API_KEY env var missing. Email marked as spam.

## Step 4: User Activation

User clicks activation link → `/activate?token={token}`:
1. Validate token (not expired, not used)
2. User sets custom username and password
3. Account marked as activated
4. Redirect to login

## Step 5: Login

`/login` (POST) — session-based authentication:
1. Validate username/password
2. Store `user_id` in Flask session
3. Redirect to dashboard

**Forgot password flow:** `/login` → "Forgot password?" link → `/forgot-password` → enter email → Brevo sends reset email with 1-hour token → `/reset-password?token=xxx` → set new password → redirect to login. Never reveals if email exists (always generic success). Rate limited to 3 requests per email per hour. Previous tokens invalidated on new request. Token functions in `account_activation.py`, routes in `ultra_simple_server.py` (lines ~6120-6207), templates: `forgot_password.html`, `reset_password.html`.

## Step 6: Broker Authentication

User connects their broker account:
- **Tradovate/NinjaTrader**: OAuth flow → `/api/oauth/callback` → stores token in `accounts.tradovate_token`
- **ProjectX**: API key entered directly → stored in `accounts.projectx_api_key`
- **Webull**: App key/secret entered → stored in `accounts.webull_app_key/secret`

**What can fail:** OAuth callback not in CSRF exempt list. Token storage fails. Tradovate credentials invalid.

## Step 7: Trader Setup

User creates a trader linking their account to a recorder:
- `POST /api/traders` with `recorder_id`, `account_id`, risk settings
- Settings inherited from recorder where not overridden (NULL fallback chain — Rule 19)
- **DCA field name bridge**: Frontend sends `avg_down_enabled`, backend stores as `dca_enabled` (Rule 24)
- JADVIX traders auto-fixed to `dca_enabled=TRUE` on every deploy

## Step 8: First Trade

TradingView alert fires → `POST /webhook/{webhook_token}`:
1. 10 webhook workers parse signal in <50ms
2. `process_webhook_directly()` finds recorder, applies filters, builds risk_config
3. Signal queued to `broker_execution_queue`
4. 10 broker workers pick up, call `execute_trade_simple()`
5. `do_trade_for_account()` runs per account simultaneously via `asyncio.gather()`
6. First entry: bracket order (entry + TP + SL in one REST call)
7. DCA entry: REST market order + separate cancel/replace TP

**What can fail:** See `docs/PAST_DISASTERS.md`. Most common: tick rounding (Rule 3), SQL placeholders (Rule 4), field name mismatches (Rule 24).

---

*Source: CLAUDE.md "USER ONBOARDING FLOW" section*
