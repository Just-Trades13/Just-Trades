# Past Disasters — Why Every Rule Exists

> **48 production disasters in ~3 months. Every rule was written in blood (lost money, lost time, lost users).**
> **Last updated: Feb 24, 2026**

---

## Disaster Summary Table

| # | Date | What Happened | Root Cause | Rule | Recovery Time |
|---|------|---------------|------------|------|---------------|
| 1 | Dec 4, 2025 | AI bulk-modified 3 files, deleted template | Batched changes | Rule 1 | Hours |
| 2 | Jan 12, 2026 | 15+ "improvements" → cascading failures | Refactored working code | Rule 2 | Hours |
| 3 | Jan 27, 2026 | 40% trade failures, missing credentials | Settings not in enabled_accounts | Rule 6 | Hours |
| 4 | Jan 28, 2026 | `failed_accounts` undefined, 30+ failures | Restructured try block | Rule 2 | Hours |
| 5 | Feb 6, 2026 | TP orders piling up (3-5 per position) | SQL `?` on PostgreSQL + cross-account TP ID | Rules 4, 5 | 2 days |
| 6 | Feb 6, 2026 | Wrong position sizes (2 instead of 1) | NULL masking in UI + missing fields in enabled_accounts | Rules 6, 19 | Hours |
| 7 | Feb 7, 2026 | TP rejected on DCA (fractional price) | Not rounding to tick_size | Rule 3 | Hours |
| 8 | Feb 7, 2026 | Cross-account TP contamination | DB has no subaccount_id column | Rule 5 | Hours |
| 9 | Feb 10, 2026 | **100% trade failure** — NameError | Rewrote override block, dropped variables | Rule 2, Sacred | Hours |
| 10 | Feb 12, 2026 | **100% OUTAGE 4+ HOURS** — mega-commit | Bundled changes, background→sync, undefined `meta` | Rules 1, 2, 20 | **4+ hours** |
| 11 | Feb 13, 2026 | TypeError: `'string' in None` | dict.get() returns None when key exists with None | Rule 17 | Hours |
| 12 | Feb 16, 2026 | Whop webhooks silently 403'd ALL day | CSRF exempt list had `/webhook/` not `/webhooks/` | Rule 23 | Hours |
| 13 | Feb 16, 2026 | Whop API calls all 401 Unauthorized | Railway env var truncated (42 of 73 chars) | Rule 21 | Hours |
| 14 | Feb 16, 2026 | Whop memberships all skipped silently | API response format wrong (string vs dict) | Rule 22 | Hours |
| 15 | Feb 17, 2026 | WebSocket multi-bracket silently failed | WebSocket pool was NEVER functional | Rule 10 | Hours |
| 16 | Feb 17, 2026 | Bracket orders stopped after signal blocking | Signal blocking changes in webhook handler | Rule 20, Sacred | Hours |
| 17 | Feb 18, 2026 | DCA-off got 1 contract instead of 3 | Two layers reacted to stale position when DCA off | Rule 12 | Hours |
| 18 | Feb 18, 2026 | Multiplier not applied to trim qty (1,1,13 instead of 5,5,5) | Raw contract count not scaled by multiplier | Rule 13 | Hours |
| 19 | Feb 18, 2026 | 12+ stale open records polluted position detection | Signal tracking ignored DCA off status | Rule 14 | Hours |
| 20 | Feb 18, 2026 | GC TPs 2.5x too far from entry | 2-letter symbol root missed tick_sizes dict | Rule 15 | Hours |
| 21 | Feb 19, 2026 | DCA toggle ON had no effect — always False | Frontend sends `avg_down_enabled`, backend reads `dca_enabled` | Rule 24 | Hours |
| 22 | Feb 20, 2026 | Trader 1359 got 0 accounts → 0 trades silently | `env` variable only defined in else-branch | Rule 25 | Hours |
| 23 | Feb 19, 2026 | Admin user delete failed — FK constraint | DELETE FROM users without cascading child records | Rule 26 | Hours |
| 24 | Feb 20-21, 2026 | **ALL activation emails failed for 2 days** | brevo-python unpinned → Docker pulled v4 → API incompatible | Rule 29 | **Hours (multi-attempt)** |
| 25 | Feb 22-23, 2026 | Copy trader: ALL follower trades 401 | Internal requests.post() no auth header | Rule 32 | Hours |
| 26 | Feb 23, 2026 | Copy trader: Token refresh overwrites valid tokens | `if refreshed:` dict truthiness always True | Rule 17, 32 | Hours |
| 27 | Feb 23, 2026 | Copy trader: Sequential follower execution | Simple `for follower in followers:` loop | `22f32be` | Minutes |
| 28 | Feb 23, 2026 | **46 FILLS PER ACCOUNT — infinite cross-leader loop** | WS fill events have no clOrdId → dedup never fires | `e6fe62d` | Minutes |
| 29 | Feb 23, 2026 | TP orders stacking 5+ deep | SQL `?` fails silently on PostgreSQL + no cancel-before-place | Phase 1 | Hours |
| 30 | Feb 23, 2026 | Position monitor never started | Startup placed in wrong file | `fb4c67e` | Hours |
| 31 | Feb 23, 2026 | Copy trader toggle stuck "Disabled" — 4 bugs | Startup reset + race condition + missing import + no session key | Rules 32-34 | Hours |
| 32 | Feb 23, 2026 | Auto-copy followers sequential | `for follower in followers:` in auto-copy path | `b26dc75` | Minutes |
| 33 | Feb 23, 2026 | Auto-copy close+re-enter on position add | Position sync always closed+re-entered instead of delta | `b97eb10` | Minutes |
| 34 | Feb 24, 2026 | **WS 429 storm — 16+ connections cycling every 90s** | Dead-sub threshold too aggressive (90s vs 300s) | `79e3f7b` | Hours |
| 35 | Feb 24, 2026 | **ALL trades 60s timeout — dead WS pool** | get_pooled_connection() tried connecting, held lock | `6efcbd5` | Hours |
| 36 | Feb 24, 2026 | **Token refresh daemon uses sqlite3 in production** | Wrong DB driver in refresh function | `d457d44` | Hours |
| 37 | Feb 24, 2026 | **max_contracts DEFAULT 10 caps ALL traders** | Migration default value too restrictive | `adb859b` | Hours |
| 38 | Feb 24, 2026 | **"Unknown error" masks EVERY failure** | Generic error return in run_async() | `27c38c5` | Hours |
| 39 | Feb 24, 2026 | **429 storm persists after Bug #34 fix** | All 16+ connections still reconnect simultaneously | `84d5091` | Hours |
| 40 | Feb 24, 2026 | **COMPLETE FIX: Semaphore gates WS connects** | asyncio.Semaphore(2) + 3s spacing | `84d5091` | **Overnight confirmed** |
| 41 | Feb 24, 2026 | **Position sizing falsy-0 → wrong contracts** | `if 0:` is False in Python | `9f34b0e` | Hours |
| 42 | Feb 24, 2026 | **DCA-off stacking: 3+3+3=9 contracts** | Old position not closed before new bracket | `78fc9fd` | Hours |
| 43 | Feb 24, 2026 | **ALL trades 60s timeout — _smart() defaults to WS** | 17 calls with use_websocket=True default | `c9e49d5`+`a214126` | Hours |
| 44 | Feb 24, 2026 | **WS crash loop — "message too big" every 13s** | websockets default max_size=1MB too small | `c3b4c5b` | Hours |
| 45 | Feb 24, 2026 | **Reversal close-only, no re-enter** | Opposite-direction DCA-off set `adjusted_quantity` but never re-entered | `83d2733` | Hours |
| 46 | Feb 24, 2026 | **CLOSE signal misrouted as SHORT** | `action='CLOSE'` → `signal_side='SHORT'` → DCA-off close+re-enter or wrong reversal | `13a217b` | Hours |
| 47 | Feb 25, 2026 | **429 reconnect storm (15 demo connections cycling)** | Per-connection backoff, no shared cooldown across connections | `2447618` | Minutes |
| 48 | Feb 25, 2026 | **CLOSE signal opens SHORT when broker flat** | Bug #46 handler requires has_existing_position=True; no-position path fell through to entry | `45d2f12` | Minutes |

---

## Key Patterns

**44 disasters in ~3 months. Average recovery: 2-4 hours each.**

Almost every one was caused by:
- (a) Editing without reading
- (b) Batching changes
- (c) Restructuring working code
- (d) Field name mismatches between frontend and backend
- (e) Auth/session assumptions for internal requests
- (f) Dead code that silently blocks live paths (#35)
- (g) Concurrent connection attempts without rate limiting (#39-40)
- (h) Python falsy semantics on numeric 0 (#41) and WebSocket library defaults (#44)

## Feb 24 Sessions — 11 BUGS IN 24 HOURS (Bugs #34-44)

1. Token refresh daemon was sqlite3 (never refreshed tokens in production)
2. max_contracts DEFAULT 10 silently capped every trader
3. "Unknown error" masked all diagnostics
4. Dead WebSocket pool blocked ALL trades with 60s timeouts
5. WS connection manager 429 storm from aggressive dead-sub detection
6. 429 storm PERSISTED because thresholds weren't enough without a semaphore
7. Legacy dead code had old thresholds that could re-trigger
8. Position sizing falsy-0: 0 fell back to 1, multiplier tripled to 9
9. DCA-off same-direction stacking: signals piled up (3+3+3=9)
10. ALL `_smart()` calls defaulted to WebSocket (hangs indefinitely) — 17 calls affected
11. WS position monitor crash loop: sync response exceeded 1MB default

**Lesson 1:** Fix DIAGNOSTIC infrastructure first, then work outward from most critical path.
**Lesson 2:** NEVER use Python falsy checks for numeric settings where 0 is valid.
**Lesson 3:** When fixing a call pattern, grep ALL instances — not just the one failing.
**Lesson 4:** Always check library defaults against expected payload sizes.

---

*Source: CLAUDE.md "PAST DISASTERS" section*
