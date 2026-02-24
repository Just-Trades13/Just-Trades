# WebSocket Fast Execution System — DEPRECATED

> **Status: DISABLED** — Feb 24, 2026 (Bugs #39, #40, #43)
> **Rule 10: ALL Tradovate orders use REST. NEVER WebSocket.**

The WebSocket order pool described in the original version of this doc was **never functional**.
It caused 60-second trade timeouts (Bug #39) and was permanently disabled in commit `6efcbd5`.

- `get_pooled_connection()` now returns `None` immediately
- All 17 `_smart()` calls use `use_websocket=False`
- The `websockets` library is still used for **monitoring** (position/fill/order sync) — NOT for orders

See CLAUDE.md Rule 10 and Rule 10b for the current WebSocket architecture.
