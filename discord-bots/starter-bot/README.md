# Just.Trades Discord Bot — Starter

A minimal, production-friendly Discord bot starter with **slash commands**.  
Built for Myles to learn step-by-step and deploy fast.

---

## 1) Prereqs
- Node.js 18+ (`node -v`)
- A Discord account + a test server you can add a bot to
- Git + GitHub

## 2) Create a Discord Application + Bot
1. Go to https://discord.com/developers/applications → **New Application**.
2. Name it (e.g., `JustTrades Bot`).
3. In **Bot** tab → **Reset Token** → copy the **Bot Token** (we'll put this in `.env`).  
4. In **OAuth2 → URL Generator**:  
   - Scopes: `bot`, `applications.commands`  
   - Bot Permissions: `Send Messages`, `Read Messages/View Channels`, `Use Slash Commands`  
   - Copy the generated URL and open it to add the bot to your server.
5. Copy the **Application ID** (aka Client ID).

## 3) Configure Environment
Copy `.env.example` → `.env` and fill:
```
DISCORD_TOKEN=your-bot-token
CLIENT_ID=your-application-id
GUILD_ID=your-test-guild-id  # optional for faster command registration
```

## 4) Install & Run
```bash
npm install
npm run register   # registers slash commands (instantly if GUILD_ID is set)
npm start          # starts the bot
```

You should see `[READY] Logged in as ...` in your terminal. In Discord, try `/ping` and `/help`.

## 5) Project Structure
```
just-trades-discord-bot/
  ├─ commands/           # add more slash commands here
  │   ├─ help.js
  │   └─ ping.js
  ├─ src/
  │   ├─ bot.js          # bot runtime
  │   └─ register.js     # command registration
  ├─ .env.example
  ├─ .gitignore
  ├─ package.json
  └─ README.md
```

## 6) Git & GitHub (quick)
```bash
git init
git add .
git commit -m "feat: bootstrap discord bot starter"
# create an empty repo on GitHub first, then:
git remote add origin https://github.com/<your-username>/just-trades-discord-bot.git
git branch -M main
git push -u origin main
```

## 7) Next Steps
- Add real commands in `commands/` (e.g., `/price`, `/calendar`, `/signal`).
- Keep secrets in `.env` (never commit `.env`).
- Deploy on Render/Railway when ready.
