import os, json, asyncio
import discord
from discord import app_commands
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
from dateutil import tz
from utils import load_json, save_json, normalize_events, window_status, upcoming, format_event_line, EVENT_STYLES

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
if not TOKEN:
    raise SystemExit("Missing DISCORD_BOT_TOKEN in environment")

CONFIG = load_json("config.json", {})
EVENTS = normalize_events(load_json("events.json", []), CONFIG.get("timezone","America/Chicago"))

INTENTS = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=INTENTS)

def local_now(tz_name):
    return datetime.now(tz.gettz(tz_name))

def utc_now():
    return datetime.utcnow().replace(tzinfo=tz.UTC)

async def post_daily_status():
    channel_id = CONFIG.get("channel_id")
    tz_name = CONFIG.get("timezone","America/Chicago")
    chan = bot.get_channel(channel_id)
    if not chan:
        return
    now = utc_now()
    active = window_status(now, EVENTS)
    upcoming_list = upcoming(now, EVENTS, days=CONFIG.get("lookahead_days",14))

    if active:
        title = "🚫 Bot PAUSED — High‑Risk Event Active"
        color = discord.Color.red()
        desc = "\n\n".join([format_event_line(e, tz_name) for e in active])
    else:
        title = "✅ Bot OK — No Active Tier‑1 Events"
        color = discord.Color.green()
        # show next event
        if upcoming_list:
            nxt = upcoming_list[0]
            desc = "Next risk window:\n" + format_event_line(nxt, tz_name)
        else:
            desc = "No upcoming events in the configured lookahead window."

    embed = discord.Embed(title=title, description=desc, color=color)
    embed.set_footer(text=f"Timezone: {tz_name}")
    await chan.send(embed=embed)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    # Schedule daily post
    sched = AsyncIOScheduler(timezone=CONFIG.get("timezone","America/Chicago"))
    hh, mm = CONFIG.get("daily_post_time","07:45").split(":")
    sched.add_job(post_daily_status, CronTrigger(hour=int(hh), minute=int(mm)))
    sched.start()
    # Sync slash commands
    try:
        if CONFIG.get("guild_id"):
            guild = discord.Object(id=CONFIG["guild_id"])
            bot.tree.copy_global_to(guild=guild)
            await bot.tree.sync(guild=guild)
        else:
            await bot.tree.sync()
        print("Slash commands synced.")
    except Exception as e:
        print("Command sync failed:", e)

# Slash Commands
@bot.tree.command(name="pause-today", description="Show whether the bot should be paused right now.")
async def pause_today(interaction: discord.Interaction):
    tz_name = CONFIG.get("timezone","America/Chicago")
    now = utc_now()
    active = window_status(now, EVENTS)
    if active:
        desc = "\n\n".join([format_event_line(e, tz_name) for e in active])
        embed = discord.Embed(title="🚫 Bot PAUSED — Active Event", description=desc, color=discord.Color.red())
    else:
        upcoming_list = upcoming(now, EVENTS, days=CONFIG.get("lookahead_days",14))
        if upcoming_list:
            nxt = upcoming_list[0]
            desc = "Next risk window:\n" + format_event_line(nxt, tz_name)
        else:
            desc = "No upcoming events."
        embed = discord.Embed(title="✅ Bot OK — No Active Tier‑1 Events", description=desc, color=discord.Color.green())
    embed.set_footer(text=f"Timezone: {tz_name}")
    await interaction.response.send_message(embed=embed, ephemeral=False)

@bot.tree.command(name="pause-calendar", description="Show next N days of pause events.")
@app_commands.describe(days="Lookahead window in days (default from config).")
async def pause_calendar(interaction: discord.Interaction, days: int | None = None):
    tz_name = CONFIG.get("timezone","America/Chicago")
    now = utc_now()
    days = days or CONFIG.get("lookahead_days",14)
    up = upcoming(now, EVENTS, days=days)
    if not up:
        await interaction.response.send_message("No events found in the lookahead window.", ephemeral=False)
        return
    lines = [format_event_line(e, tz_name) for e in up]
    embed = discord.Embed(title=f"🚫 Bot Pause Calendar — Next {days} days",
                          description="\n\n".join(lines),
                          color=discord.Color.orange())
    embed.set_footer(text=f"Timezone: {tz_name}")
    await interaction.response.send_message(embed=embed, ephemeral=False)

def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.manage_guild

@bot.tree.command(name="pause-add", description="Admin: Add a one‑off pause event.")
@app_commands.describe(title="Event title (e.g., CPI, FOMC)",
                       start="Start datetime (YYYY-MM-DD HH:MM) in configured timezone",
                       end="End datetime (YYYY-MM-DD HH:MM) in configured timezone",
                       type="Event type (CPI, NFP, FOMC, FED, PPI, GDP, ISM, EARN, OTHER)",
                       notes="Optional notes")
async def pause_add(interaction: discord.Interaction, title: str, start: str, end: str, type: str="OTHER", notes: str=""):
    if not is_admin(interaction):
        await interaction.response.send_message("You need **Manage Server** permission to use this.", ephemeral=True)
        return
    tz_name = CONFIG.get("timezone","America/Chicago")
    new_event = {
        "title": title,
        "type": type.upper(),
        "start_local": start,
        "end_local": end,
        "notes": notes
    }
    global EVENTS
    EVENTS.append(new_event)
    EVENTS = normalize_events(EVENTS, tz_name)
    save_json("events.json", EVENTS)
    await interaction.response.send_message(f"Added event **{title}** from `{start}` to `{end}` ({type.upper()}).", ephemeral=False)

@bot.tree.command(name="pause-remove", description="Admin: Remove an event by its id (use /pause-calendar to see ids).")
async def pause_remove(interaction: discord.Interaction, event_id: str):
    if not is_admin(interaction):
        await interaction.response.send_message("You need **Manage Server** permission to use this.", ephemeral=True)
        return
    global EVENTS
    before = len(EVENTS)
    EVENTS = [e for e in EVENTS if e.get("id") != event_id]
    save_json("events.json", EVENTS)
    removed = before - len(EVENTS)
    await interaction.response.send_message(f"Removed {removed} event(s) with id `{event_id}`.", ephemeral=False)

if __name__ == "__main__":
    bot.run(TOKEN)
