import discord
import asyncio
import os
import pandas as pd
import investpy
from dotenv import load_dotenv
import requests
from textblob import TextBlob

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
else:
    print("❌ Error: .env file not found!")

# Discord Bot Token & Channel IDs (loaded from .env)
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
BREAKING_NEWS_CHANNEL_ID = int(os.getenv("BREAKING_NEWS_CHANNEL_ID", "0"))
LIVE_TRADES_CHANNEL_ID = int(os.getenv("LIVE_TRADES_CHANNEL_ID", "0"))
TRADE_SETUPS_CHANNEL_ID = int(os.getenv("TRADE_SETUPS_CHANNEL_ID", "0"))

# Initialize bot
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Store last alerts to prevent spam
last_trade_alert = None
last_sentiment_alert = None
last_news_alert = None

def fetch_news():
    """Fetches top market news headlines."""
    url = "https://newsapi.org/v2/top-headlines?category=business&language=en&apiKey=YOUR_NEWSAPI_KEY"
    response = requests.get(url)
    articles = response.json().get("articles", [])
    if articles:
        return [(article["title"], article["url"]) for article in articles[:5]]
    return []

async def send_news_alerts():
    """Fetch and send breaking news alerts."""
    global last_news_alert
    channel = client.get_channel(BREAKING_NEWS_CHANNEL_ID)

    news = fetch_news()
    if not news:
        return

    for title, url in news:
        message = f"📰 **{title}**\n🔗 {url}"
        if message != last_news_alert:
            last_news_alert = message
            await channel.send(message)

def get_futures_price(symbol):
    """Fetch real-time futures price from Investing.com"""
    try:
        if symbol == "NQ=F":
            data = investpy.get_index_recent_data(index="Nasdaq 100", country="united states", as_json=False)
        elif symbol == "ES=F":
            data = investpy.get_index_recent_data(index="S&P 500", country="united states", as_json=False)
        else:
            return None

        if not data.empty:
            return data["Close"].iloc[-1]
        else:
            print(f"⚠️ No data found for {symbol} on Investing.com")
            return None

    except Exception as e:
        print(f"❌ Error fetching {symbol} price from Investing.com: {e}")
        return None

async def send_trade_setups():
    """Analyze market data and send trade setup alerts with direction."""
    global last_trade_alert
    channel = client.get_channel(TRADE_SETUPS_CHANNEL_ID)

    nq_price = get_futures_price("NQ=F")
    es_price = get_futures_price("ES=F")

    if nq_price:
        direction = "🟢 **Bullish**" if nq_price > 20250 else "🔴 **Bearish**"
        target_price = nq_price + 30 if nq_price > 20250 else nq_price - 30
        stop_loss = nq_price - 15 if nq_price > 20250 else nq_price + 15
        message = f"📊 **NQ Trade Setup:** {direction} \nEntry: {nq_price:.2f} \nTarget: {target_price:.2f} \nStop Loss: {stop_loss:.2f}"
        if message != last_trade_alert:
            last_trade_alert = message
            await channel.send(message)

    if es_price:
        direction = "🟢 **Bullish**" if es_price > 5100 else "🔴 **Bearish**"
        target_price = es_price + 25 if es_price > 5100 else es_price - 25
        stop_loss = es_price - 10 if es_price > 5100 else es_price + 10
        message = f"📊 **ES Trade Setup:** {direction} \nEntry: {es_price:.2f} \nTarget: {target_price:.2f} \nStop Loss: {stop_loss:.2f}"
        if message != last_trade_alert:
            last_trade_alert = message
            await channel.send(message)

async def send_live_trade_signals():
    """Determine sentiment and send live trade call-outs with specific price conditions."""
    global last_sentiment_alert
    channel = client.get_channel(LIVE_TRADES_CHANNEL_ID)

    nq_price = get_futures_price("NQ=F")

    if nq_price:
        threshold = 20250
        sentiment = "🟢 **Bullish over**" if nq_price > threshold else "🔴 **Bearish under**"
        message = f"🔥 **NQ Live Trade Callout:** {sentiment} {threshold} \nCurrent Price: {nq_price:.2f}"
        if message != last_sentiment_alert:
            last_sentiment_alert = message
            await channel.send(message)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    while True:
        await send_news_alerts()
        await send_trade_setups()
        await send_live_trade_signals()
        await asyncio.sleep(60)  # Runs every 1 minute for fast trades

client.run(TOKEN)

