# Tradovate OAuth Grant Flow

> Source: Live capture on 2025-11-08 using TradersPost Trade Manager onboarding. All credentials redacted. Use this document to rebuild the `/v1/auth/oauthgrant` integration with resilient error handling.

## 1. Sequence Overview

1. **Bootstrap**
   - Collect Tradovate username/password via TradersPost UI (never store plaintext client-side after submission).
   - Retrieve TradersPost-managed `cid` / `sec` pair (stored server-side).
   - Generate `deviceId` (UUID) and start authorization session server-side.
2. **Authorization Code Request**
   - `POST https://live.tradovateapi.com/v1/auth/authorize`
   - Body (application/json):
     ```json
     {
       "name": "<username>",
       "password": "<password>",
       "appId": "TradersPost",
       "cid": "<client_id>",
       "sec": "<client_secret>",
       "deviceId": "<uuid>",
       "redirectUri": "https://app.traderspost.io/oauth/callback",
       "state": "<csrf_token>"
     }
     ```
   - Response provides short-lived `code`; fallback to `https://demo.tradovateapi.com` for demo accounts.
3. **Access Token Exchange**
   - `POST https://live.tradovateapi.com/v1/auth/oauthgrant`
   - Body captured in `tradovate-oauth.md` (authorization code grant).
   - Persist `accessToken`, `refreshToken`, `mdAccessToken`, `expirationTime` for user.
4. **Account Hydration**
   - Immediately call `GET /v1/users/me` and `/v1/accounts/list` with bearer token to populate broker account metadata.
   - Store `userId`, account list, and link tokens to TradersPost account record.

## 2. Error Handling & Retries

| Failure | Symptom | Handling Strategy |
| --- | --- | --- |
| `401 Unauthorized` | Invalid credentials or revoked app ID | Prompt user to re-enter credentials; lock account after 3 attempts. |
| `403 Forbidden` | App not whitelisted / incorrect redirect URI | Confirm client credentials; fallback to demo endpoint; alert ops channel. |
| `429 Too Many Requests` | Tradovate rate limiting | Exponential backoff (base 2s, max 30s) with jitter; cap at 3 retries. |
| Network timeouts | Request > 10s | Retry up to 2 times; switch between live/demo endpoints if applicable. |
| `code` expired | OAuth grant fails after delay | Re-run authorization step to obtain new `code`. |

All retries must be **server-side**. Never re-send user credentials from the browser after initial submission.

## 3. Token Lifecycle

- `accessToken` – trade execution token (Bearer), expires quickly (minutes).
- `refreshToken` – exchange token, long-lived; store encrypted at rest.
- `mdAccessToken` – market data token, required for chart streams.
- `expirationTime` – ISO timestamp; refresh 60 seconds before expiry.

### Refresh Strategy

1. Track `token_expires_at` (`expirationTime`) per account.
2. Use `/v1/auth/renewaccess` with refresh token to rotate before expiry.
3. If refresh fails with `401`, restart full OAuth grant to obtain new tokens.

## 4. Demo vs Live Switch

- Detect demo accounts via user selection or account prefix (`DEMO`).
- Replace base URL with `https://demo.tradovateapi.com` for both authorize and grant requests.
- Maintain separate token stores for live vs demo to avoid cross-environment leakage.

## 5. Implementation Checklist

- [ ] Server endpoint to accept credentials and trigger OAuth flow.
- [ ] Secrets vault storage for `cid`, `sec`, and Tradovate refresh tokens.
- [ ] Encrypted database columns for access/refresh tokens + expiry metadata.
- [ ] Retry utilities (exponential backoff + jitter) shared across Tradovate calls.
- [ ] Audit logging (success/failure, account ID, error codes) without exposing credentials.
- [ ] Unit tests covering success, credential failure, rate limiting, and token refresh.
- [ ] Integration test using demo endpoint with mocked responses to validate full handshake.

