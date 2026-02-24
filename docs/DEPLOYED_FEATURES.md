# Deployed Features — Just Trades Platform

> **Complete list of stable, confirmed-working features in production.**
> **Last updated: Feb 24, 2026**

---

## What's Working (28 Settings Verified)

**Execution**: Enable/disable, initial/add position size, multiplier, max contracts
**TP**: Targets (ticks + trim %), units (Ticks/Points/Percent), trim_units (Contracts/Percent)
**SL**: Enable/amount, units, type (Fixed/Trailing), trail trigger/freq
**Risk**: Break-even (toggle/ticks/offset), DCA (amount/point/units)
**Filters**: Signal cooldown, max signals/session, max daily loss, add delay, time filters 1&2
**Other**: Custom ticker, inverse strat, auto flat after cutoff

---

## Feature Deployment History

| Feature | Commit | Date | Status |
|---------|--------|------|--------|
| Flip close cleanup (cancels resting orders) | `d531455` | Feb 13 | Confirmed on JADMGC |
| NoneType crash fix (`or` instead of default) | `d6f5f4a` | Feb 13 | Working |
| Whop sync daemon (30s poll, auto-create accounts) | `ce19d18` | Feb 16 | Working |
| CSRF fix for Whop webhooks | `ce19d18` | Feb 16 | Working |
| Native multi-bracket orders (multi-leg TP + trail) | `8f61062` | Feb 17 | Confirmed LIVE |
| Time filter status on Control Center | `9470ca5` | Feb 18 | Working |
| DCA-off bracket fix | `c75d7d4` | Feb 18 | Confirmed on all 4 recorders |
| Multiplier trim scaling | `201d498` | Feb 18 | Confirmed |
| ProjectX parity (opposite block, DCA SL, trailing) | `c9f0a3d` | Feb 13 | **UNTESTED** |
| User delete cascade (all child tables) | `a40fc07` | Feb 19 | Working |
| Insider signals admin bypass | `4e95998` | Feb 19 | Working |
| DCA field name fix (avg_down_enabled → dca_enabled) | `d3e714d` | Feb 19 | **Confirmed LIVE** |
| SSE real-time price streaming to dashboard | `8641182` | Feb 20 | Working |
| TradingView WebSocket JWT auth fix (was crashing) | `d43cd0c` | Feb 20 | **Needs verification** |
| JADVIX DCA auto-enable on startup | `bda90af` | Feb 19 | **Confirmed LIVE** |
| env UnboundLocalError fix in enabled_accounts | `656683a` | Feb 20 | Working |
| Tick size 2-letter symbol root fix (GC, CL, SI) | `656683a` | Feb 20 | Working |
| Broker-verified quantity safety net (DB/broker drift) | `bb1a183` | Feb 20 | Working |
| Brevo v1 pin + start.sh runtime install (activation emails) | `5b6be75` | Feb 21 | **Confirmed working** |
| Pro Copy Trader pricing card + sidebar gating + route locks | `99f990c` | Feb 22 | Working |
| TOS + Risk Disclosure updated with Goldman-reviewed legal language | `993d8b5` | Feb 22 | Working |
| Forgot password system (Brevo email + token reset, 1hr expiry) | `bd95145`..`9f8a7e1` | Feb 22 | **Needs verification** |
| Pro Copy Trader: PLATFORM_URL fix (localhost→127.0.0.1:PORT) | `e67add9` | Feb 22 | Working |
| Pro Copy Trader: Manual trade follower propagation (BUY/SELL/CLOSE) | `aa176a4` | Feb 22 | **Confirmed working** |
| Pro Copy Trader: Auto-mode toggle reload signal (5s pickup) | `4f854c5` | Feb 22 | Working |
| Pro Copy Trader: Auth gate bypass (X-Admin-Key for internal requests) | `03c5853` | Feb 23 | **Confirmed working** |
| Pro Copy Trader: Token refresh truthy dict fix + 85-min expiry | `b7529f9` | Feb 23 | **Confirmed working** |
| Pro Copy Trader: Parallel follower propagation (ThreadPoolExecutor) | `22f32be` | Feb 23 | **Confirmed working** |
| Pro Copy Trader: Cross-leader loop prevention (time-based dedup) | `e6fe62d` | Feb 23 | **CRITICAL FIX** |
| Pro Copy Trader: Pipeline separation (skip followers with webhook traders) | `e46c4a4` | Feb 23 | Working |
| TP Order Stacking Fix: SQL placeholders in reconciliation | Phase 1 | Feb 23 | **Confirmed working** |
| TP Order Stacking Fix: Symbol matching + status list | Phase 1 | Feb 23 | **Confirmed working** |
| TP Order Stacking Fix: Cancel-before-place + duplicate cleanup | Phase 1 | Feb 23 | **Confirmed working** |
| WebSocket Position Monitor (`ws_position_monitor.py`) | `636ae87` | Feb 23 | **Confirmed working** |
| WS Position Monitor startup integration | `fb4c67e` | Feb 23 | **Confirmed working** |
| Reconciliation downgraded to 5-min safety net | Phase 2 | Feb 23 | Working |
| WS monitors: market-hours reconnect fix | `2c53a6d` | Feb 23 | **Confirmed working** |
| Copy trader toggle: remove startup force-OFF reset | `ef813fe` | Feb 23 | **Confirmed working** |
| Copy trader toggle: optimistic UI + race condition fix | `39b8122` | Feb 23 | **Confirmed working** |
| Copy trader toggle: missing get_user_by_id import fix | `ce4e6a2` | Feb 23 | **Confirmed working** |
| FLASK_SECRET_KEY set as permanent Railway env var | N/A | Feb 23 | **CRITICAL — sessions survive deploys** |
| Auto-copy: parallel follower execution (asyncio.gather) | `b26dc75` | Feb 23 | **Confirmed working** |
| Auto-copy: add-to-position instead of close+re-enter | `b97eb10` | Feb 23 | **Confirmed working** |
| Copy trader: warning disclaimer (don't mix with webhooks) | `24e1094` | Feb 23 | Working |
| Paper trading accuracy: multiplier, DCA-off, trader overrides, trim scaling | `32ad0ab`..`a819a22` | Feb 23 | **Needs verification** |
| Shared WS Connection Manager (1-2 connections instead of 6-12) | `f1795c3` | Feb 23 | **Confirmed working** |
| WS Connection Manager: 429 storm fix (10x30s dead-sub, 30s stagger, 30s backoff) | `79e3f7b` | Feb 24 | **Confirmed working — ZERO 429s post-deploy** |
| Dead WebSocket pool disabled (`get_pooled_connection()` returns None) | `6efcbd5` | Feb 24 | **CRITICAL — eliminates 60s trade timeouts** |
| WS Connection Semaphore: asyncio.Semaphore(2) + 3s spacing on connects | `84d5091` | Feb 24 | **CRITICAL — stops 429 storm. Overnight hold confirmed Feb 24→25. NEVER REMOVE.** |
| WS Legacy dead-sub thresholds hardened to >= 10 in ALL 4 locations | `84d5091` | Feb 24 | **Confirmed working** |
| Token refresh daemon PostgreSQL fix (was sqlite3 in production) | `d457d44` | Feb 24 | **Confirmed working** |
| Unknown error diagnostic fix (propagates run_async exceptions) | `27c38c5` | Feb 24 | **Confirmed working** |
| max_contracts DEFAULT 10→0 migration (uncapped 172 traders) | `adb859b` | Feb 24 | **CRITICAL — silent trade cap removed** |
| Position sizing falsy-0 fix (4 locations: webhook qty detection, initial/add size, broker safety net) | `9f34b0e` | Feb 24 | **Confirmed working — py_compile passed** |
| DCA-off close-before-open (cancel resting orders + close position before fresh bracket) | `78fc9fd` | Feb 24 | **Confirmed working — py_compile passed** |
| Frontend: allow position sizes of 0 in trader form | `c5d72b4` | Feb 24 | Working |
| ALL `_smart()` calls forced REST-only (`use_websocket=False` on 17 calls) | `c9e49d5`+`a214126` | Feb 24 | **CRITICAL — eliminates 60s trade timeouts on ALL code paths** |
| WS crash loop fix: `max_size=10MB` + `splitResponses=true` on shared connection manager | `c3b4c5b` | Feb 24 | **Confirmed — ZERO crash loops post-deploy, all 19 listeners connected** |

---

## Supported Brokers

| Broker | Status | Auth Type | Notes |
|--------|--------|-----------|-------|
| **Tradovate** | Working | OAuth + Credentials | Primary broker, full integration |
| **NinjaTrader** | Working | Same as Tradovate | Uses Tradovate API backend |
| **ProjectX/TopstepX** | Working | API Key | Prop firm support |
| **Webull** | Working | App Key/Secret | Stocks, options, futures |
| **Rithmic** | Coming Soon | - | Not implemented |

---

*Source: CLAUDE.md "DEPLOYED FEATURES" and "WHAT'S WORKING" sections*
