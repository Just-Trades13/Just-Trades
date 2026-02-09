# Just Trades Discord Ticket Bot

A custom Discord ticket support system for the Just Trades community.

## Features

- 🎫 **Ticket Categories**: Trading Support, Billing, Technical Issues, General
- 📝 **Transcript Logging**: Automatic transcript generation when tickets close
- 👥 **Role-based Access**: Support team gets pinged and can view all tickets
- 📊 **Statistics**: Track ticket volume and status
- ⚡ **Slash Commands**: Modern Discord slash command interface

## Setup

### 1. Create Discord Application

1. Go to https://discord.com/developers/applications
2. Click "New Application" → Name it "Just Trades Support"
3. Go to "Bot" → Click "Add Bot"
4. **Copy the Bot Token** (you'll need this)
5. Enable Privileged Gateway Intents:
   - ✅ Server Members Intent
   - ✅ Message Content Intent
6. Go to "OAuth2" → "URL Generator"
7. Select scopes: `bot`, `applications.commands`
8. Select permissions:
   - Manage Channels
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Manage Messages
   - Manage Roles
9. Copy the URL and invite bot to your server

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your values:
- `DISCORD_TOKEN` - Your bot token
- `CLIENT_ID` - Your application ID (from General Information)
- `GUILD_ID` - Already set to Just Trades server

### 3. Install & Run

```bash
npm install
npm start
```

## Commands

| Command | Description | Permission |
|---------|-------------|------------|
| `/setup` | Configure ticket system | Admin |
| `/panel` | Create ticket panel | Manage Channels |
| `/close [reason]` | Close current ticket | Everyone |
| `/claim` | Claim a ticket | Everyone |
| `/stats` | View ticket statistics | Manage Channels |

## First-Time Setup

After inviting the bot:

1. **Create a ticket category** in Discord (e.g., "Support Tickets")
2. **Create a log channel** (e.g., #ticket-logs)
3. **Run setup command**:
   ```
   /setup category:#Support-Tickets support_role:@Support log_channel:#ticket-logs
   ```
4. **Create the ticket panel**:
   ```
   /panel channel:#open-ticket
   ```

## Deployment

### Railway (Recommended)

1. Push to GitHub
2. Connect repo to Railway
3. Add environment variables in Railway dashboard
4. Deploy!

### VPS/Server

```bash
npm install -g pm2
pm2 start src/index.js --name just-trades-tickets
pm2 save
pm2 startup
```

## Support

For issues with this bot, contact the Just Trades dev team.
