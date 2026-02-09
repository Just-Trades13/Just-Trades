from discord.ext import commands
from typing import Optional, Dict, Any
import discord
import os
import aiohttp
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
import pytz

from src.bots.base_bot import TradingBot

class MarketDataBot(TradingBot):
    def __init__(self, command_prefix: str = "!", **options):
        super().__init__(command_prefix, "market_data_bot", **options)
        self.session: Optional[aiohttp.ClientSession] = None
        self.last_news_update: Dict[str, datetime] = {}
        
    async def setup_hook(self) -> None:
        """Setup tasks before bot connects."""
        await super().setup_hook()
        self.session = aiohttp.ClientSession()
        self.logger.info("Market Data Bot setup complete")
        
    async def close(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
        await super().close()
        
    async def get_stock_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get stock data for a given symbol."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Get historical data for the last 2 days
            hist = ticker.history(period="2d")
            if hist.empty:
                return None
                
            # Calculate change
            prev_close = hist['Close'].iloc[-2]
            current_price = hist['Close'].iloc[-1]
            change = current_price - prev_close
            change_percent = (change / prev_close) * 100
            
            return {
                'symbol': symbol.upper(),
                'price': current_price,
                'change': change,
                'change_percent': change_percent,
                'name': info.get('shortName', symbol.upper()),
                'day_high': hist['High'].iloc[-1],
                'day_low': hist['Low'].iloc[-1],
                'volume': hist['Volume'].iloc[-1],
                'prev_close': prev_close,
                'timestamp': datetime.now(pytz.UTC)
            }
        except Exception as e:
            self.logger.error(f"Error getting stock data for {symbol}: {e}")
            return None
            
    async def format_stock_embed(self, data: Dict[str, Any]) -> discord.Embed:
        """Format stock data into a Discord embed."""
        # Determine color based on price change
        color = 0x00ff00 if data['change'] >= 0 else 0xff0000
        
        embed = discord.Embed(
            title=f"📊 {data['name']} ({data['symbol']})",
            color=color,
            timestamp=data['timestamp']
        )
        
        # Add price and change
        change_emoji = "📈" if data['change'] >= 0 else "📉"
        embed.add_field(
            name="Price",
            value=f"**${data['price']:.2f}** {change_emoji} "
                  f"({data['change']:+.2f} | {data['change_percent']:+.2f}%)",
            inline=False
        )
        
        # Add day range and volume
        embed.add_field(
            name="Day Range",
            value=f"**High:** ${data['day_high']:.2f}\n"
                  f"**Low:** ${data['day_low']:.2f}",
            inline=True
        )
        
        embed.add_field(
            name="Volume",
            value=f"{data['volume']:,}",
            inline=True
        )
        
        # Add previous close
        embed.add_field(
            name="Previous Close",
            value=f"${data['prev_close']:.2f}",
            inline=True
        )
        
        return embed
        
    async def get_news(self, query: Optional[str] = None, limit: int = 5) -> list:
        """Get financial news."""
        try:
            api_key = os.getenv('NEWS_API_KEY')
            if not api_key:
                self.logger.warning("NEWS_API_KEY not set")
                return []
                
            params = {
                'apiKey': api_key,
                'category': 'business',
                'language': 'en',
                'pageSize': limit
            }
            
            if query:
                params['q'] = query
                
            url = 'https://newsapi.org/v2/top-headlines' if not query else 'https://newsapi.org/v2/everything'
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                return data.get('articles', [])[:limit]
        except Exception as e:
            self.logger.error(f"Error fetching news: {e}")
            return []
            
    def format_news_embed(self, article: Dict[str, Any]) -> discord.Embed:
        """Format a news article into a Discord embed."""
        embed = discord.Embed(
            title=article.get('title', 'No title')[:256],
            url=article.get('url', ''),
            description=article.get('description', '')[:2048] or None,
            color=0x1a73e8,
            timestamp=datetime.strptime(article.get('publishedAt', ''), '%Y-%m-%dT%H:%M:%SZ') if article.get('publishedAt') else None
        )
        
        if article.get('urlToImage'):
            embed.set_image(url=article['urlToImage'])
            
        if article.get('source', {}).get('name'):
            embed.set_footer(text=f"Source: {article['source']['name']}")
            
        return embed

# Command line entry point
def main():
    """Run the Market Data Bot."""
    bot = MarketDataBot()
    
    @bot.command(name='stock')
    async def stock(ctx, symbol: str):
        """Get stock data for a given symbol."""
        async with ctx.typing():
            data = await bot.get_stock_data(symbol)
            if not data:
                await ctx.send(f"❌ Could not find data for {symbol}")
                return
                
            embed = await bot.format_stock_embed(data)
            await ctx.send(embed=embed)
    
    @bot.command(name='news')
    async def news(ctx, query: Optional[str] = None, limit: int = 5):
        """Get financial news."""
        if limit > 10:
            limit = 10
            
        async with ctx.typing():
            articles = await bot.get_news(query, limit)
            if not articles:
                await ctx.send("❌ No news found")
                return
                
            for article in articles:
                embed = bot.format_news_embed(article)
                await ctx.send(embed=embed)
    
    bot.run()

if __name__ == "__main__":
    main()
