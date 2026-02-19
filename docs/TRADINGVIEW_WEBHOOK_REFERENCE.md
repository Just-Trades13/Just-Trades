# TradingView Webhook & Alert System — Developer Reference

> **Purpose**: Technical reference for receiving TradingView webhooks at `POST /webhook/{token}`
> **Target response time**: < 50ms (queue async, return 200 immediately)
> **Last verified**: Feb 18, 2026

---

## CRITICAL NUMBERS — QUICK REFERENCE

```
INBOUND WEBHOOK:
  Method:       POST
  Content-Type: application/json (if valid JSON) or text/plain
  Body:         Raw alert message with resolved placeholders
  Source IPs:   52.89.214.238, 34.212.75.30, 54.218.53.128, 52.32.178.7
  Ports:        80, 443 only
  Protocol:     HTTPS required (SSL validated)
  Timeout:      3 seconds max
  Retry:        3x at 5s intervals on 5xx (except 504); NO retry on 4xx/timeout

YOUR RESPONSE:
  Status:       200 OK
  Body:         Anything (ignored by TradingView)
  Target time:  < 50ms (return 200, queue async processing)

RATE LIMITS:
  Per alert:    15 triggers per 3 minutes
  Consequence:  Alert auto-disabled (SILENT — no notification)

PLAN REQUIRED: Plus or higher (no webhooks on Free/Essential)
```

---

## 1. Webhook POST Request

### HTTP Headers

| Header | Value |
|--------|-------|
| Method | `POST` |
| Content-Type (JSON body) | `application/json; charset=utf-8` |
| Content-Type (plain text body) | `text/plain; charset=utf-8` |

TradingView auto-detects: if alert message is valid JSON → `application/json`; otherwise `text/plain`. No configurable User-Agent.

### Request Body

The body contains **exactly** the text from the alert's "Message" field, with all `{{placeholders}}` resolved. No envelope or wrapper — the message IS the body.

```
POST /webhook/{token} HTTP/1.1
Content-Type: application/json; charset=utf-8

{"action":"buy","ticker":"NQH6","price":21450.25,"time":"2026-02-18T14:30:00Z"}
```

### Source IP Addresses (Allowlist)

```
52.89.214.238
34.212.75.30
54.218.53.128
52.32.178.7
```

### Constraints

- Ports **80** and **443** only
- **HTTPS required** (TradingView validates SSL certificates)
- IPv6 **not supported**
- 2FA must be enabled on the TradingView account for webhooks

---

## 2. Response Requirements & Timeout

| Constraint | Value |
|------------|-------|
| **Max response time** | **3 seconds** (TradingView cancels after this) |
| **Required response code** | Any `2xx` (200 preferred) |
| **Recommended response time** | < 300ms for safety margin |

**Our pattern**: Parse/validate synchronously, queue to `broker_execution_queue`, return 200 immediately.

---

## 3. Retry Behavior

| Scenario | Behavior |
|----------|----------|
| **5xx response (500-599, except 504)** | 3 retries at 5-second intervals (4 total attempts) |
| **504 Gateway Timeout** | **No retry** |
| **4xx response (400-499)** | **No retry** — signal is LOST |
| **3xx redirects** | **No retry** — not followed |
| **Timeout (> 3 seconds)** | **No retry** |
| **DNS failure / unreachable** | **No retry** |
| **SSL/TLS error** | **No retry** |

### Implications for Just Trades

- **NEVER return 4xx** for transient failures — you lose the signal permanently
- **NEVER return 5xx** intentionally — only 3 retries at 5s intervals
- **ALWAYS return 200 immediately** and handle errors internally
- Design for **idempotency** — same webhook may arrive up to 4 times on 5xx retries
- Deduplication: hash of `(ticker + action + timenow)` with 30-second window

---

## 4. Rate Limits

| Limit | Value |
|-------|-------|
| Max triggers | **15 per 3 minutes** per alert |
| Consequence | Alert **auto-disabled** (SILENT — no notification) |

- 1-minute chart = 1/min (safe)
- 5-second chart = 12/min (will hit limit)
- **"Once per bar close"** is safest for automated systems
- If auto-disabled, NO notification sent — monitor externally

---

## 5. All Available Placeholders

### Standard Placeholders (ALL Alert Types)

| Placeholder | Returns | Example |
|-------------|---------|---------|
| `{{ticker}}` | Symbol ticker | `AAPL`, `NQH6` |
| `{{exchange}}` | Exchange name | `NASDAQ`, `CME_MINI` |
| `{{interval}}` | Chart timeframe | `5`, `60`, `D` |
| `{{close}}` | Bar close price | `21450.25` |
| `{{open}}` | Bar open price | `21448.50` |
| `{{high}}` | Bar high price | `21452.00` |
| `{{low}}` | Bar low price | `21447.75` |
| `{{volume}}` | Bar volume | `1523` |
| `{{time}}` | Bar open time (UTC) | `2026-02-18T14:30:00Z` |
| `{{timenow}}` | Alert fire time (UTC) | `2026-02-18T14:30:01Z` |
| `{{syminfo.currency}}` | Quote currency | `USD` |
| `{{syminfo.basecurrency}}` | Base currency (crypto/forex) | `BTC` |
| `{{plot_0}}`–`{{plot_19}}` | Indicator output values | `75.32` |
| `{{plot("RSI")}}` | Indicator by plot title | `68.5` |

### Strategy-Specific Placeholders (Strategy Alerts Only)

| Placeholder | Returns | Example |
|-------------|---------|---------|
| `{{strategy.order.action}}` | `"buy"` or `"sell"` | `buy` |
| `{{strategy.order.contracts}}` | Contracts filled | `3` |
| `{{strategy.order.price}}` | Fill price | `21450.25` |
| `{{strategy.order.id}}` | Order ID string | `"Long Entry"` |
| `{{strategy.order.comment}}` | Order comment | `"DCA Add"` |
| `{{strategy.order.alert_message}}` | Dynamic `alert_message` param | (dynamic) |
| `{{strategy.market_position}}` | Position after fill | `long`, `short`, `flat` |
| `{{strategy.market_position_size}}` | Abs position size after fill | `6` |
| `{{strategy.prev_market_position}}` | Position before fill | `flat`, `long` |
| `{{strategy.prev_market_position_size}}` | Abs size before fill | `3` |
| `{{strategy.position_size}}` | Signed position size | `-3` |

---

## 6. Strategy vs. Indicator Alerts

| Feature | Strategy Alerts | Indicator Alerts |
|---------|----------------|------------------|
| Trigger source | Order fill events | `alert()` or `alertcondition()` |
| `{{strategy.*}}` placeholders | All available | None |
| Multiple fires per alert | Yes (one per fill) | Controlled by `freq` param |
| Dynamic messages | `alert_message` parameter | `alert()`: series string |
| One alert = many signals | Yes | One per condition |

Each order fill = one separate webhook POST.

---

## 7. JSON Format (Recommended)

### Static JSON Template (Alert Message field)

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

### Per-Order Dynamic Message (Pine Script)

```pine
strategy.entry("Long", strategy.long,
    alert_message='{"action":"buy","qty":' + str.tostring(qty) + '}')
```
Alert Message field: `{{strategy.order.alert_message}}`

---

## 8. Common Signal Formats for Copy-Trading

### Our Platform's Format (Token in URL)

```
POST /webhook/{webhook_token}
```

```json
{
    "action": "buy",
    "ticker": "NQH6",
    "quantity": 3,
    "price": 21450.25,
    "position": "long",
    "time": "2026-02-18T14:30:01Z"
}
```

### Common Action Values

| Action | Meaning | Aliases |
|--------|---------|---------|
| `buy` | Enter long / Add to long | `long`, `enter_long` |
| `sell` | Enter short / Add to short | `short`, `enter_short` |
| `closelong` | Close long position | `exit_long`, `close_buy` |
| `closeshort` | Close short position | `exit_short`, `close_sell` |
| `close` | Close any position | `exit`, `flatten`, `flat` |

---

## 9. Edge Cases & Gotchas

### Placeholder Resolution Failures
- Strategy placeholder in non-strategy alert → empty string
- `{{plot_0}}` returns value at trigger time, may differ from bar close
- `{{time}}` = bar open time; `{{timenow}}` = alert fire time

### JSON Validity After Resolution
```json
// Template (valid):
{"comment": "{{strategy.order.comment}}"}
// Resolved (INVALID — unescaped quotes):
{"comment": "Take Profit "TP1""}
```
**Defense**: Always `try/except` around `json.loads()`.

### Multiple Fills Per Bar
One bar can generate multiple fills. Each = separate webhook POST. Queue and process sequentially per ticker.

### Alert Auto-Disable (Silent)
- Hit 15 triggers in 3 minutes
- TradingView plan expires/downgrades
- Alert expiration time passes
- No notification — monitor externally

### Duplicate Signals on 5xx Retry
If server returns 500 but processed the signal, TradingView retries 3x. Could place 4x trades. Dedup with `(ticker + action + timenow)` hash.

---

## Sources

- [TradingView Webhook Configuration](https://www.tradingview.com/support/solutions/43000529348-how-to-configure-webhook-alerts/)
- [Webhook Resubmission / Retry](https://www.tradingview.com/support/solutions/43000735201-webhook-resubmission/)
- [Strategy Alerts](https://www.tradingview.com/support/solutions/43000481368-strategy-alerts/)
- [Using Variables in Alerts](https://www.tradingview.com/support/solutions/43000531021-how-to-use-a-variable-value-in-alert/)
- [Alert Rate Limit](https://www.tradingview.com/support/solutions/43000690939-alert-was-triggered-too-often-and-stopped/)
- [Webhook Error Meanings](https://www.tradingview.com/support/solutions/43000776894-what-do-errors-mean-when-sending-webhooks/)
- [Pine Script Alerts Docs](https://www.tradingview.com/pine-script-docs/concepts/alerts/)

*Source: TradingView documentation + production experience with Just Trades platform*
