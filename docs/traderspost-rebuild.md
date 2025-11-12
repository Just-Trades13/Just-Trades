# TradersPost Rebuild Plan & Log

> **Note for all collaborators:** This document is the canonical handoff/coordination file. Read it before starting work, claim your tasks here, and update the checklist + work log as you go so every window knows the current status.

## 1. Scope Overview
- **Goal:** Recreate the TradersPost Trade Manager UI and backend experiences.
- **Reference Assets:** HTML snapshots, CSS bundle, and network payloads collected from the live product (stored in `docs/assets/`).
- **Primary Component Areas:**
  - Sidebar (`App:LeftMenu`)
  - Page header + dashboard CTA row
  - `Trading:Broker:*` components (summary tiles, account manager table, balance snippets, connection status card)
  - Onboarding/setup modals (`setup-steps`, `change-plan`)
  - Tradovate OAuth integration and downstream API contracts

## 2. Component Checklist
| Component / Feature | Owner | Status | Notes |
| --- | --- | --- | --- |
| Sidebar (`App:LeftMenu`) | @assistant | ☐ TODO | Phase 1 – rebuild layout from captured HTML once tokens ready (markup archived) |
| Dashboard header / CTA row | @assistant | ☐ TODO | Phase 1 – align breadcrumbs + CTA wiring with layout pass |
| `Trading:Broker:BrokerAccountSummary` card | @assistant | ☐ TODO | Phase 2 – wire into dashboard summary endpoints (`broker-widget-mapping.md`) |
| `Trading:Broker:BrokerAccountManager` table | @assistant | ☐ TODO | Phase 2 – build table w/ filters + action handlers (`broker-widget-mapping.md`) |
| `Trading:Broker:BrokerAccountBalance` snippet | @assistant | ☐ TODO | Phase 2 – pending balance payload capture (see mapping doc) |
| `Trading:Broker:Connect:CheckConnectionStatus` | @assistant | ☐ TODO | Phase 2 – success/reconnect states based on sync stub |
| Modals (`setup-steps`, `change-plan`) | @assistant | ☐ TODO | Phase 2 – port modal markup + state machine |
| Tradovate OAuth handshake | @assistant | ☐ TODO | Phase 3 – implement `/v1/auth/oauthgrant` dance |
| API contract definitions | @assistant | ☐ TODO | Phase 3 – catalog `refreshAccounts`, summary, etc. |
| CSS tokenization / theme setup | @assistant | ☐ IN PROGRESS | Phase 0 – extract utility map + set theme variables (tokens json ready) |

Legend: ☐ TODO / ☐ IN PROGRESS / ☑ DONE

### Execution Blueprint (2025-11-09)
- **Phase 0 – Asset Intake:** Create `docs/assets/html`, `docs/assets/css`, `docs/assets/network`, and `docs/assets/auth` directories, ingest captured files, and extract initial design tokens.
- **Phase 1 – Layout & Navigation:** Rebuild `App:LeftMenu` and dashboard header using tokenized styles; ensure responsive structure and CTA wiring.
- **Phase 2 – Broker Workflows:** Implement broker summary, balances, account manager table, connection status, and onboarding modals using captured JSON payloads.
- **Phase 3 – Auth & Sync:** Reproduce Tradovate OAuth grant flow, stub account refresh endpoints, and document API contracts with validation.
- **Phase 4 – QA & Polish:** Add turbo stream updates, automated checks, and deployment-ready documentation.

## 3. Assets Library
- `docs/assets/html/dashboard-dump.html` – full dashboard capture with inline styles/scripts.
- `docs/assets/html/app-left-menu.html` – extracted markup for `App:LeftMenu`.
- `docs/assets/html/dashboard-header.html` – navbar/header strip including user controls.
- `docs/assets/html/performance-cards.html` – dashboard KPI card grid.
- `docs/assets/html/trade-history-table.html` – trade table + pagination block.
- `docs/assets/css/app.84022a8b.css` – full utility + theme bundle (copied from `main.edcc780c.css` capture).
- `docs/assets/css/design-tokens.json` – parsed `:root` design tokens from CSS bundle.
- `docs/assets/network/samples/accounts.get.sample.json` – sanitized `GET /api/accounts/` payload.
- `docs/assets/network/samples/dashboard.summary.sample.json` – representative dashboard summary metrics.
- `docs/assets/network/schemas/accounts.list.contract.json` – JSON schema for account listing response.
- `docs/assets/network/schemas/accounts.refresh.contract.json` – contract for refreshing Tradovate subaccounts.
- `docs/assets/network/schemas/dashboard.summary.contract.json` – schema for dashboard summary aggregates.
- `docs/assets/network/broker-widget-mapping.md` – component-to-payload mapping notes.
- `docs/assets/auth/tradovate-oauth.md` – sanitized authentication request/response notes.
- `docs/assets/auth/tradovate-oauth-flow.md` – step-by-step OAuth grant + retry strategy blueprint.

> Create folders/files as they are populated. This section doubles as a manifest.

## 4. Work Log
| Date | Window/User | Task | Notes / Links |
| --- | --- | --- | --- |
| 2025-11-08 | @myles | Collected dashboard HTML dump | Saved to `docs/assets/html/dashboard-dump.html` |
| 2025-11-08 | @myles | Captured Tradovate OAuth grant request headers + payload | Sanitized request noted in `docs/assets/auth/tradovate-oauth.md` |
| 2025-11-09 | @assistant | Established execution blueprint + asset inventory | Created assets folder structure, CSS bundle copy, token extract, HTML slices, OAuth capture, API schemas, and OAuth flow blueprint |

(Add rows chronologically as work progresses.)

## 5. Next Actions
- [x] Create `docs/assets/html`, `docs/assets/css`, `docs/assets/network`, and `docs/assets/auth` structure; move captured files into place.
- [x] Extract and catalogue core design tokens from `app.84022a8b.css`.
- [x] Slice dashboard HTML dump into component files (`App:LeftMenu`, header, broker widgets).
- [x] Define API contract JSON schemas for `refreshAccounts`, summary, and related endpoints.
- [x] Draft Tradovate OAuth handshake flow with retry/error handling scaffolding.
- [x] Map broker-specific widgets (summary, balances, manager table) to decoded payloads once assets are available.

## 6. Open Questions / Risks
- Need to confirm additional broker API calls beyond `refreshAccounts` before backend work.
- Decide final frontend tech stack (TeleportHQ export vs custom React/Vue) to avoid rework.
- Establish testing plan to validate data accuracy (balances, subscription counts, etc.).

---

_Keep this document updated as the single source of truth for cross-window collaboration._
