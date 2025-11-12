# Broker Widget Data Mapping

> Canonical reference tying UI components to captured API payloads. Use this when rebuilding Phase 2 broker surfaces (`Trading:Broker:*`).

## `Trading:Broker:BrokerAccountSummary`

- **Primary endpoint:** `GET /api/dashboard/summary/`
- **Schema reference:** `docs/assets/network/schemas/dashboard.summary.contract.json`
- **Sample payload:** `docs/assets/network/samples/dashboard.summary.sample.json`

| UI Element | HTML Reference | Data Field | Notes |
| --- | --- | --- | --- |
| Total Strategies card | `performance-cards.html` → card title `Total ROI` (front card variant to be updated with live copy) | `total_strategies` | Render as integer with thousands separator. |
| Active Positions card | Same file, icon `fa-layer-group` | `active_positions` | Display as integer, highlight non-zero counts. |
| Lifetime P&L | Same file, card category `TOTAL ROI` | `total_pnl` | Format as currency with sign (+/-). |
| Today P&L | Same file, card category `RETURN` | `today_pnl` | Currency format; zero state shows `$0`. |
| Last updated timestamp (optional) | N/A (append to card footer) | `updated_at` | Field may be null; if present show relative time (“Updated 2m ago”). |

> **Open item:** Additional performance tiles (`W_L_WinRate`, `Drawdown`, `Profit Factor`, etc.) require `GET /api/dashboard/analytics/` captures. Plan to record payload once access to live environment resumes.

## `Trading:Broker:BrokerAccountManager`

- **Primary endpoint:** `GET /api/accounts/`
- **Schema reference:** `docs/assets/network/schemas/accounts.list.contract.json`
- **Sample payload:** `docs/assets/network/samples/accounts.get.sample.json`

| UI Element | HTML / React Source | Data Field | Notes |
| --- | --- | --- | --- |
| Card title | `app-left-menu.html` (nav) & `AccountManagement.jsx` header | `name` (fallback `username`) | Preserve casing from payload; fall back gracefully. |
| Platform badge | `AccountManagement.jsx` line 149 | `platform` | Default to `Tradovate` if null. |
| Status badge | CSS class `status-badge` | `disabled` & `status` | Show “Disabled” when `disabled = true`, else display `status || 'Active'`. |
| Sub-account list | Flip-card back (to be rebuilt) | `subAccounts[*].name`, `subAccounts[*].active` | Include tag chips when `tags` array provided (e.g., Demo/Live). |
| Bulk actions | Account grid toolbar | Derived from selected account IDs | Rely on `id` for selection and API mutations (delete, refresh). |

> **Future capture:** `POST /api/accounts/{id}/refresh/` returns refreshed token metadata. UI should refresh account list after success via `GET /api/accounts/`.

## `Trading:Broker:BrokerAccountBalance`

- **Pending capture:** Balance snippet data is emitted by a yet-to-be-recorded endpoint (likely `refreshAccounts` Turbo stream or `/api/accounts/balances/`).
- **Known requirements from live UI:** 
  - Current account balance (formatted currency)
  - Open P&L
  - Buying power / margin available
  - Timestamp of latest sync or streaming update

**Action plan**
1. Capture the balance payload during the next HAR logging session (target the “Balance” widget refresh in live app).
2. Define JSON schema under `docs/assets/network/schemas/` mirroring the captured response.
3. Update this mapping with explicit field bindings and include a sanitized sample.

Until the payload is captured, treat the balance widget as **blocked** for implementation and surface this dependency in sprint planning.

