# Just.Trades — Bot Pause Calendar (Discord)

A lightweight Discord bot that posts **"Bot Pause"** alerts for high‑risk market events
(NFP, CPI, FOMC, etc.) and provides slash commands to view / manage the pause calendar.

## Features
- Daily auto‑post (time configurable) in your channel with **today's pause status**.
- Slash commands:
  - `/pause-today` — Shows whether to pause now + the events affecting the session.
  - `/pause-calendar` — Shows the next 14 days of pause events.
  - `/pause-add` — Admin‑only: Add a one‑off event from Discord (persists to `events.json`).
  - `/pause-remove` — Admin‑only: Remove an event by ID (from `events.json`).
- Simple **JSON storage** (no database) and **timezone aware** (uses IANA tz like `America/Chicago`).
- Opinionated default event types and colors (CPI, NFP, FOMC, PPI, GDP, ISM, Fed Speeches, etc.).

> Works out‑of‑the‑box without external APIs. You can manually maintain `events.json`,
> or later plug in your own fetcher (TradingEconomics, FinancialJuice, etc.) to populate it.

---

## Quick Start (Replit)
1. Create a new **Python** Replit and upload these files.
2. In Replit **Secrets** add:
   - `DISCORD_BOT_TOKEN` – your bot token.
3. Edit `config.json`:
   - `guild_id` (optional), `channel_id` (where to post), `timezone`, `daily_post_time` (HH:MM 24h).
4. Run the repl. On first run it will create an app command tree and sync slash commands.

### Keep Alive on Replit
Replit now supports **Always On** for paid plans. If not available, you can use a pinger service
+ a small web server; this template focuses on core bot logic.

---

## File Overview
- `bot.py` — main entry; loads config, schedules daily post, defines slash commands.
- `utils.py` — event utilities (load/save, overlap checks, formatting).
- `events.json` — your curated list of **pause events** with ISO datetimes and labels.
- `config.json` — bot settings (channel, tz, daily post time, lookahead horizon).
- `requirements.txt` — python dependencies.
- `Procfile` — optional (for platforms like Heroku / Railway); not required for Replit.

---

## Example: Adding Events
1) **Manual**: Edit `events.json` and add entries (example entries already included).
2) **From Discord** (admin only):
   ```
   /pause-add title:"CPI" start:"2025-10-10 08:30" end:"2025-10-10 10:00" type:"CPI"
   ```

> All times are in your configured timezone (`config.json`). The bot converts to UTC internally.

---

## Safety Defaults
- The bot recommends **PAUSE** during any active event window.
- You can customize colors / emojis and what counts as **Tier‑1** inside `utils.py` (EVENT_STYLES).

---

## Notes
- This template stores data in `events.json`. For teams, keep it in Git or mount a small DB later.
- If you later want **automatic population** from an API, create a cron that writes to `events.json`
  in the same schema.
