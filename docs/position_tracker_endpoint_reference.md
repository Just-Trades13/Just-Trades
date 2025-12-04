## Position Tracker Endpoint Reference (Legacy)

These HTTP routes were previously wired to the position-tracking service. Keep them noted for when we rebuild the tracker so the front end knows where to reconnect.

| Endpoint | Method | Purpose |
| --- | --- | --- |
| `/api/positions/<account_id>/start` | POST | Spin up a live tracker for the specified account (websocket + polling). |
| `/api/positions/<account_id>/stop` | POST | Tear down the tracker and release websocket resources. |
| `/api/positions/<account_id>` | GET | Return the latest cached positions (symbol, qty, avg price, last price, unrealized PnL). |
| `/api/positions/<account_id>/status` | GET | Lightweight health check to see if the tracker is currently running for the account. |

> All of these routes lived inside `ultra_simple_server.py`; when we implement the next iteration we can either reuse the same paths or update this document with the new mapping.

