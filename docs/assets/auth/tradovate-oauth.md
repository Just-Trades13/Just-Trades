# Tradovate OAuth Handshake (Sanitized Capture)

## Source
- Captured November 8, 2025 from TradersPost Trade Manager onboarding flow.
- Environment: `https://live.tradovateapi.com`.

## Request
- **Method:** `POST`
- **Path:** `/v1/auth/oauthgrant`
- **Headers:**
  - `Content-Type: application/json`
  - `Accept: application/json`
  - `User-Agent: TradersPost/1.0 (Darwin; OAuthClient)`
  - `X-Forwarded-For: <redacted>`
- **Body:**
```json
{
  "name": "<username>",
  "password": "<password>",
  "appId": "TradersPost",
  "appVersion": "1.0.0",
  "deviceId": "1d7f0c90-2df4-4cb9-9156-1a5b1fbd4bf1",
  "cid": "<client_id>",
  "sec": "<client_secret>",
  "code": "<oauth_authorization_code>",
  "grant_type": "authorization_code",
  "redirect_uri": "https://app.traderspost.io/oauth/callback"
}
```

> Credentials (`name`, `password`, `cid`, `sec`) and authorization `code` are redacted. Device UUID retained from capture.

## Response
- **Status:** `200 OK`
- **Headers:** Standard JSON payload, cache-control disabled.
- **Body (snipped):**
```json
{
  "accessToken": "<access_token>",
  "refreshToken": "<refresh_token>",
  "mdAccessToken": "<market_data_token>",
  "tokenType": "Bearer",
  "userId": 123456,
  "expirationTime": "2025-11-08T18:21:47.000Z",
  "scope": "trade account:read account:write md"
}
```

## Notes
- Response includes both trading (`accessToken`) and market-data (`mdAccessToken`) tokens.
- TradersPost repeats the grant for demo users by swapping the base URL to `https://demo.tradovateapi.com`.
- Subsequent calls poll `/v1/users/me` with the bearer token to hydrate account metadata.

