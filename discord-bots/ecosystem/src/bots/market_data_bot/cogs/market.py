import discord
from discord.ext import commands
from typing import Optional


class MarketCog(commands.Cog):
    """Market data commands — stock prices and financial news."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='stock')
    async def stock(self, ctx, symbol: str):
        """Get stock data for a given symbol. Usage: !stock AAPL"""
        async with ctx.typing():
            data = await self.bot.get_stock_data(symbol)
            if not data:
                await ctx.send(f"Could not find data for {symbol.upper()}")
                return
            embed = await self.bot.format_stock_embed(data)
            await ctx.send(embed=embed)

    @commands.command(name='news')
    async def news(self, ctx, query: Optional[str] = None, limit: int = 5):
        """Get financial news. Usage: !news [query] [limit]"""
        if limit > 10:
            limit = 10
        async with ctx.typing():
            articles = await self.bot.get_news(query, limit)
            if not articles:
                await ctx.send("No news found")
                return
            for article in articles:
                embed = self.bot.format_news_embed(article)
                await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(MarketCog(bot))
