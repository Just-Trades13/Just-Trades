# Account Management Snapshot — November 25, 2025

This snapshot captures the exact state of the account management UI and backend logic that the user approved. **Do not modify these pieces without explicit approval.**

## Key Files

- `templates/account_management.html`
- `ultra_simple_server.py`
- Backup copies stored in `backups/2025-11-25/`

## Frontend Guarantees

- Manual cards show:
  - Account name
  - Connection status (green/red)
  - Broker badge
  - Live account number (green) and Demo account number (orange)
  - Refresh + Reconnect buttons only (no extra controls/icons)
  - Delete icon remains for removing the account
- Refresh button:
  - Shows spinner, disables button, calls `/api/accounts/<id>/refresh-subaccounts`
  - Re-enables after completion and reloads cards
- No extra header buttons except `+ Add Account`

## Backend Guarantees

- `/api/accounts`:
  - Parses both `subaccounts` and `tradovate_accounts`
  - Fields include `has_demo` and `has_live`
- `fetch_and_store_tradovate_accounts`:
  - Uses both `https://demo.tradovateapi.com` and `https://live.tradovateapi.com`
  - Adds `environment` + `is_demo` to each account
  - Stores combined list plus formatted subaccounts
- Refresh endpoint (`POST /api/accounts/<id>/refresh-subaccounts`) calls the function above, so both live and demo numbers stay in sync.

## OAuth Flow

- Redirects to `https://trader.tradovate.com/oauth` (scope `All`, state carries `account_id`)
- Callback always uses client ID `8699`, secret `7c74576b-20b1-4ea5-a2a0-eaeb11326a95`
- Tokens are exchanged via `https://demo.tradovateapi.com/v1/auth/oauthtoken`
- After token storage, `fetch_and_store_tradovate_accounts` runs automatically

## How to Restore

1. Checkout the saved commit or backup files:
   ```bash
   git checkout <snapshot-commit> -- templates/account_management.html ultra_simple_server.py
   ```
   or copy from `backups/2025-11-25/`.
2. Restart the server:
   ```bash
   pkill -f "python.*ultra_simple_server"
   nohup python3 ultra_simple_server.py > server.log 2>&1 &
   ```
3. Refresh `/accounts` via ngrok and verify live/demo lines plus refresh/reconnect buttons.

## Notes

- This is the baseline for future changes. Any modifications must be documented and re-snapshotted.
- If Tradovate API credentials change, update them only after duplicating this file and the backups folder for the new state.


