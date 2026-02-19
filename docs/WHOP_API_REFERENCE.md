# Whop API Reference — Just Trades Platform

> **Purpose**: Membership/payment integration via Whop
> **API Version**: v1 REST + v2/v5 Webhooks (response formats differ!)
> **Official docs**: https://docs.whop.com
> **Last verified**: Feb 18, 2026

---

## CRITICAL: RESPONSE FORMAT DIFFERS BY API VERSION

| Context | `product` | `user` | `email` |
|---------|-----------|--------|---------|
| **v1 REST API** | Object `{"id": "prod_xxx", "title": "..."}` | Object `{"id": "user_xxx", "email": "..."}` | Nested: `user.email` |
| **v2/v5 Webhooks** | **String** `"prod_xxx"` | **String** `"user_xxx"` | **Top-level**: `data.email` |
| **v2 REST (no expand)** | **String** `"prod_xxx"` | String/varies | Top-level `email` |

**ALWAYS use `isinstance()` checks.** See Safe Parsing Pattern below.

---

## AUTHENTICATION

### Header Format

```
Authorization: Bearer YOUR_API_KEY
Content-Type: application/json
```

### API Key Types

| Prefix | Type | Use Case |
|--------|------|----------|
| `biz_*` | Company API Key | Your own company data |
| `app_*` | App API Key | Multi-company apps |

### Required Permissions

- `member:basic:read` — List/retrieve memberships
- `member:email:read` — Access user email
- `webhook_receive:memberships` — Receive webhook events

### Environment Variables

```bash
WHOP_API_KEY=biz_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx          # Full key, 73+ chars
WHOP_WEBHOOK_SECRET=whsec_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx  # Full secret
```

**WARNING**: Railway truncates long env vars in table display. Always verify with `railway variables --kv` (CLAUDE.md Rule 21).

---

## MEMBERSHIP ENDPOINTS

### List Memberships

```
GET https://api.whop.com/api/v1/memberships
```

**Key Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `company_id` | string | Your company ID (`biz_*`) |
| `after` | string | Cursor for pagination |
| `first` | integer | Return first N elements |
| `statuses[]` | array | Filter: `active`, `trialing`, etc. |
| `product_ids[]` | array | Filter by product IDs |

**Response:**

```json
{
  "data": [
    {
      "id": "mem_xxxxxxxxxxxxxx",
      "status": "active",
      "user": {
        "id": "user_xxxxxxxxxxxxx",
        "email": "john@example.com"
      },
      "product": {
        "id": "prod_xxxxxxxxxxxxx",
        "title": "Pro Plan"
      },
      "license_key": "A1B2C3-D4E5F6-G7H8I9"
    }
  ],
  "page_info": {
    "end_cursor": "base64_cursor",
    "has_next_page": true
  }
}
```

### Retrieve Membership

```
GET https://api.whop.com/api/v1/memberships/{id}
```

`{id}` can be membership ID (`mem_*`) or license key.

### Other Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `PATCH` | `/memberships/{id}` | Update metadata |
| `POST` | `/memberships/{id}/cancel` | Cancel membership |
| `POST` | `/memberships/{id}/resume` | Resume canceled membership |
| `POST` | `/memberships/{id}/pause` | Pause payment collection |
| `POST` | `/memberships/{id}/add_free_days` | Add free days |

---

## WEBHOOK EVENTS

### v1 Events (docs.whop.com)

| Event | Description |
|-------|-------------|
| `membership.activated` | Membership becomes valid |
| `membership.deactivated` | Membership becomes invalid |
| `payment.succeeded` | Payment processed |
| `payment.failed` | Payment failed |

### v2/v5 Events (dev.whop.com)

| Event | Description |
|-------|-------------|
| `membership.went_valid` | Membership becomes valid |
| `membership.went_invalid` | Membership becomes invalid |
| `payment.succeeded` | Payment succeeded |
| `payment.failed` | Payment failed |

### v1 Webhook Payload (membership.activated)

```json
{
  "action": "membership.activated",
  "data": {
    "id": "mem_xxxxxxxxxxxxxx",
    "status": "active",
    "user": {
      "id": "user_xxxxxxxxxxxxx",
      "email": "john@example.com"
    },
    "product": {
      "id": "prod_xxxxxxxxxxxxx",
      "title": "Pro Plan"
    },
    "license_key": "A1B2C3-D4E5F6-G7H8I9"
  }
}
```

### v2/v5 Webhook Payload (membership.went_valid)

```json
{
  "action": "membership.went_valid",
  "data": {
    "id": "mem_DWWmfqMNSk5TVF",
    "product": "prod_xxxxxxxxxxxxx",
    "user": "user_xxxxxxxxxxxxx",
    "email": "john@example.com",
    "status": "active",
    "valid": true,
    "license_key": "A1B2C3-D4E5F6-G7H8I9"
  }
}
```

**Note the differences:** v2/v5 has `product` as string, `user` as string, `email` at top level.

---

## WEBHOOK SIGNATURE VERIFICATION

Uses [Standard Webhooks](https://www.standardwebhooks.com/) spec with HMAC-SHA256.

### Headers

| Header | Description |
|--------|-------------|
| `webhook-id` | Unique delivery ID (use as idempotency key) |
| `webhook-timestamp` | Unix timestamp |
| `webhook-signature` | HMAC-SHA256 signature |

### Signed Content Format

```
{webhook-id}.{webhook-timestamp}.{raw_body}
```

### Verification (Python)

```python
import hmac, hashlib, base64, time

def verify_whop_webhook(request_body, headers, secret):
    webhook_id = headers.get("webhook-id")
    webhook_timestamp = headers.get("webhook-timestamp")
    webhook_signature = headers.get("webhook-signature")

    if not all([webhook_id, webhook_timestamp, webhook_signature]):
        return False

    # Reject old timestamps (5 min tolerance)
    try:
        if abs(time.time() - int(webhook_timestamp)) > 300:
            return False
    except ValueError:
        return False

    # Build signed content
    body_str = request_body.decode("utf-8") if isinstance(request_body, bytes) else request_body
    signed_content = f"{webhook_id}.{webhook_timestamp}.{body_str}"

    # Strip 'whsec_' prefix if present
    if secret.startswith("whsec_"):
        secret_bytes = base64.b64decode(secret[6:])
    else:
        secret_bytes = base64.b64decode(secret)

    # Compute expected signature
    expected = base64.b64encode(
        hmac.new(secret_bytes, signed_content.encode("utf-8"), hashlib.sha256).digest()
    ).decode("utf-8")

    # Check against all signatures in header (format: "v1,{sig1} v1,{sig2}")
    for sig in webhook_signature.split(" "):
        parts = sig.split(",", 1)
        if len(parts) == 2 and parts[0] == "v1":
            if hmac.compare_digest(expected, parts[1]):
                return True
    return False
```

---

## SAFE PARSING PATTERN

```python
def extract_product_id(membership):
    """Works with v1 objects, v2/v5 strings, and flat fields."""
    product = membership.get("product")
    if isinstance(product, dict):
        return product.get("id")        # v1 API
    elif isinstance(product, str):
        return product                   # v2/v5 webhook
    return membership.get("product_id")  # v5 flat fallback

def extract_user_email(membership):
    """Checks top-level first (v2/v5), then nested (v1)."""
    email = membership.get("email")
    if email:
        return email
    user = membership.get("user")
    if isinstance(user, dict):
        return user.get("email")
    return None

def extract_user_id(membership):
    user = membership.get("user")
    if isinstance(user, dict):
        return user.get("id")           # v1 API
    elif isinstance(user, str):
        return user                      # v2/v5 webhook
    return membership.get("user_id")    # v5 flat fallback
```

---

## MEMBERSHIP STATUSES

| Status | Description | Has Access |
|--------|-------------|:---:|
| `trialing` | Free trial period | Yes |
| `active` | Paid, active | Yes |
| `canceling` | Cancellation pending (end of period) | Yes |
| `past_due` | Payment failed, grace period | Varies |
| `completed` | Finite membership completed | No |
| `canceled` | User canceled | No |
| `expired` | Membership expired | No |
| `unresolved` | Needs manual resolution | No |
| `drafted` | Draft, not yet active | No |

**Valid statuses for sync daemon:**

```python
VALID_STATUSES = {"trialing", "active", "canceling"}
```

---

## RATE LIMITS

| Detail | Value |
|--------|-------|
| Cooldown on limit hit | **60 seconds** |
| Exact threshold | Not publicly documented |
| Scope | Per API key |

**Sync daemon**: Poll no more than every **30 seconds**. Paginate with `first` + `after`. Filter by `statuses[]=active`.

---

## GOTCHAS — PRODUCTION LESSONS

1. **v1 vs v2/v5 response format** — `product` and `user` are objects in v1, strings in v2/v5. Always use `isinstance()` checks.
2. **Email location varies** — v1: `user.email` (nested), v2/v5: `membership.email` (top-level). Check both.
3. **Railway truncates env vars** — `WHOP_API_KEY` (73+ chars) shows 42 chars in table. Use `railway variables --kv`.
4. **CSRF exempt for `/webhooks/`** — Route is `/webhooks/whop` (plural S), not `/webhook/whop`.
5. **`access_pass` deprecated** — Use `product`, fall back to `access_pass` only if missing.
6. **Timestamps differ** — v1: ISO 8601 strings, v2/v5: Unix epoch seconds.
7. **dict.get() with None** — Use `data.get("email") or "unknown"` not `data.get("email", "unknown")` (CLAUDE.md Rule 17).
8. **Return 2xx immediately** — Process async. Whop retries on non-2xx.

---

## THREE-LAYER PROTECTION (Our Architecture)

1. **Whop webhook** (`/webhooks/whop`) — Real-time on purchase
2. **Sync daemon** (30s poll) — Catches missed webhooks
3. **Manual sync button** — Admin panel fallback

---

## Sources

- [Whop API Getting Started](https://docs.whop.com/developer/api/getting-started)
- [Whop Webhooks Guide](https://docs.whop.com/developer/guides/webhooks)
- [List Memberships](https://docs.whop.com/api-reference/memberships/list-memberships)
- [Whop Webhook Events v5](https://dev.whop.com/webhooks/v5)
- [Standard Webhooks Spec](https://www.standardwebhooks.com/)
- [Whop Rate Limits](https://dev.whop.com/api-reference/v5/rate-limits)

*Source: Whop API docs + production experience with Just Trades platform*
