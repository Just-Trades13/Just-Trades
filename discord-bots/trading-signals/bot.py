import discord
import asyncio
import os
import logging
from dotenv import load_dotenv
import aiohttp

# Load environment variables
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('trading-signals')

# Discord Bot Token & Channel IDs (loaded from .env)
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
BREAKING_NEWS_CHANNEL_ID = int(os.getenv("BREAKING_NEWS_CHANNEL_ID", "0"))
LIVE_TRADES_CHANNEL_ID = int(os.getenv("LIVE_TRADES_CHANNEL_ID", "0"))
TRADE_SETUPS_CHANNEL_ID = int(os.getenv("TRADE_SETUPS_CHANNEL_ID", "0"))

# API keys
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
ALPACA_API_KEY = os.getenv("ALPACA_API_KEY", "")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY", "")
ALPACA_ENDPOINT = os.getenv("ALPACA_ENDPOINT", "https://paper-api.alpaca.markets/v2")

if not TOKEN:
    raise SystemExit("Missing DISCORD_BOT_TOKEN in .env")

# Initialize bot
intents = discord.Intents.default()
client = discord.Client(intents=intents)

# Store last alerts to prevent spam
last_trade_alert = None
last_sentiment_alert = None
last_news_alert = None

# HTTP session for async requests
session = None


async def get_futures_snapshot(symbol: str) -> dict | None:
    """
    Fetch real-time futures data from Alpaca Markets API.
    Returns dict with price, change, prev_close or None on failure.

    symbol: Alpaca futures symbol, e.g. 'NQ' for Nasdaq 100 E-mini, 'ES' for S&P 500 E-mini
    """
    global session
    if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
        logger.warning("Alpaca API keys not configured")
        return None

    try:
        # Use Alpaca data API for latest quote
        url = f"https://data.alpaca.markets/v1beta1/screener/stocks/most-actives"
        headers = {
            "APCA-API-KEY-ID": ALPACA_API_KEY,
            "APCA-API-SECRET-KEY": ALPACA_SECRET_KEY
        }

        # For futures, use the snapshot endpoint
        # Alpaca uses /NQH6, /ESH6 style symbols for futures
        snapshot_url = f"https://data.alpaca.markets/v1beta1/snapshots?symbols={symbol}&feed=delayed"
        async with session.get(snapshot_url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                if symbol in data:
                    snap = data[symbol]
                    latest = snap.get('latestTrade', {})
                    price = latest.get('p', 0)
                    prev = snap.get('prevDailyBar', {}).get('c', price)
                    return {
                        'price': price,
                        'prev_close': prev,
                        'change': price - prev,
                        'change_pct': ((price - prev) / prev * 100) if prev else 0
                    }
            else:
                logger.warning(f"Alpaca snapshot returned {resp.status} for {symbol}")
                return None
    except Exception as e:
        logger.error(f"Error fetching {symbol} from Alpaca: {e}")
        return None


async def get_index_price(symbol: str) -> dict | None:
    """
    Fetch index/stock price from Yahoo Finance (no API key needed).
    Fallback if Alpaca doesn't work for futures.

    symbol: Yahoo Finance symbol, e.g. 'NQ=F' for Nasdaq futures, 'ES=F' for S&P futures
    """
    global session
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=2d"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with session.get(url, headers=headers) as resp:
            if resp.status == 200:
                data = await resp.json()
                result = data.get('chart', {}).get('result', [])
                if result:
                    closes = result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                    if len(closes) >= 2:
                        prev = closes[-2]
                        current = closes[-1]
                        if current and prev:
                            return {
                                'price': current,
                                'prev_close': prev,
                                'change': current - prev,
                                'change_pct': ((current - prev) / prev * 100)
                            }
                    elif len(closes) == 1 and closes[0]:
                        return {
                            'price': closes[0],
                            'prev_close': closes[0],
                            'change': 0,
                            'change_pct': 0
                        }
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol} from Yahoo: {e}")
        return None


async def fetch_news() -> list:
    """Fetches top market news headlines using NewsAPI."""
    global session
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY not configured")
        return []

    try:
        url = f"https://newsapi.org/v2/top-headlines?category=business&language=en&pageSize=5&apiKey={NEWSAPI_KEY}"
        async with session.get(url) as resp:
            if resp.status == 200:
                data = await resp.json()
                articles = data.get("articles", [])
                return [(a["title"], a.get("url", "")) for a in articles[:5] if a.get("title")]
            else:
                logger.warning(f"NewsAPI returned status {resp.status}")
                return []
    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []


async def send_news_alerts():
    """Fetch and send breaking news alerts."""
    global last_news_alert
    channel = client.get_channel(BREAKING_NEWS_CHANNEL_ID)
    if not channel:
        return

    news = await fetch_news()
    if not news:
        return

    for title, url in news:
        message = f"📰 **{title}**\n🔗 {url}"
        if message != last_news_alert:
            last_news_alert = message
            try:
                await channel.send(message)
            except Exception as e:
                logger.error(f"Error sending news alert: {e}")


async def send_trade_setups():
    """Analyze market data and send trade setup alerts with dynamic levels."""
    global last_trade_alert
    channel = client.get_channel(TRADE_SETUPS_CHANNEL_ID)
    if not channel:
        return

    # Try Alpaca first, fall back to Yahoo Finance
    nq_data = await get_index_price("NQ=F")
    es_data = await get_index_price("ES=F")

    if nq_data and nq_data['price'] > 0:
        price = nq_data['price']
        change_pct = nq_data['change_pct']
        prev = nq_data['prev_close']

        # Dynamic direction based on price vs previous close
        direction = "🟢 **Bullish**" if price > prev else "🔴 **Bearish**"
        is_bull = price > prev

        # Dynamic targets based on ATR-like range (0.15% of price)
        target_offset = price * 0.0015
        sl_offset = price * 0.0008

        target_price = price + target_offset if is_bull else price - target_offset
        stop_loss = price - sl_offset if is_bull else price + sl_offset

        message = (
            f"📊 **NQ Trade Setup:** {direction}\n"
            f"Entry: {price:,.2f} ({change_pct:+.2f}% vs prev close)\n"
            f"Target: {target_price:,.2f}\n"
            f"Stop Loss: {stop_loss:,.2f}"
        )
        if message != last_trade_alert:
            last_trade_alert = message
            try:
                await channel.send(message)
            except Exception as e:
                logger.error(f"Error sending NQ setup: {e}")

    if es_data and es_data['price'] > 0:
        price = es_data['price']
        change_pct = es_data['change_pct']
        prev = es_data['prev_close']

        direction = "🟢 **Bullish**" if price > prev else "🔴 **Bearish**"
        is_bull = price > prev

        target_offset = price * 0.0012
        sl_offset = price * 0.0006

        target_price = price + target_offset if is_bull else price - target_offset
        stop_loss = price - sl_offset if is_bull else price + sl_offset

        message = (
            f"📊 **ES Trade Setup:** {direction}\n"
            f"Entry: {price:,.2f} ({change_pct:+.2f}% vs prev close)\n"
            f"Target: {target_price:,.2f}\n"
            f"Stop Loss: {stop_loss:,.2f}"
        )
        if message != last_trade_alert:
            last_trade_alert = message
            try:
                await channel.send(message)
            except Exception as e:
                logger.error(f"Error sending ES setup: {e}")


async def send_live_trade_signals():
    """Determine sentiment and send live trade call-outs based on price action."""
    global last_sentiment_alert
    channel = client.get_channel(LIVE_TRADES_CHANNEL_ID)
    if not channel:
        return

    nq_data = await get_index_price("NQ=F")

    if nq_data and nq_data['price'] > 0:
        price = nq_data['price']
        prev = nq_data['prev_close']
        change_pct = nq_data['change_pct']

        # Dynamic sentiment based on % change from previous close
        if change_pct > 0.3:
            sentiment = "🟢 **Strong Bullish**"
        elif change_pct > 0:
            sentiment = "🟢 **Mildly Bullish**"
        elif change_pct > -0.3:
            sentiment = "🔴 **Mildly Bearish**"
        else:
            sentiment = "🔴 **Strong Bearish**"

        message = (
            f"🔥 **NQ Live Trade Callout:** {sentiment}\n"
            f"Current Price: {price:,.2f} ({change_pct:+.2f}%)\n"
            f"Previous Close: {prev:,.2f}"
        )
        if message != last_sentiment_alert:
            last_sentiment_alert = message
            try:
                await channel.send(message)
            except Exception as e:
                logger.error(f"Error sending live signal: {e}")


@client.event
async def on_ready():
    global session
    logger.info(f"Logged in as {client.user}")
    session = aiohttp.ClientSession()

    while True:
        try:
            await send_news_alerts()
            await send_trade_setups()
            await send_live_trade_signals()
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
        await asyncio.sleep(300)  # Run every 5 minutes


import time

max_retries = 5
for attempt in range(max_retries):
    try:
        client.run(TOKEN)
        break  # Clean shutdown
    except discord.errors.HTTPException as e:
        if e.status == 429:
            wait = min(30 * (2 ** attempt), 300)  # 30s, 60s, 120s, 240s, 300s
            logger.warning(f"Rate limited by Discord (attempt {attempt+1}/{max_retries}). Waiting {wait}s...")
            time.sleep(wait)
            # Recreate client — old one's internal session is dead after failed login
            client = discord.Client(intents=intents)
            client.event(on_ready)
        else:
            logger.error(f"Discord HTTP error: {e}")
            break
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        break
else:
    logger.error("Max retries exceeded. Exiting.")
