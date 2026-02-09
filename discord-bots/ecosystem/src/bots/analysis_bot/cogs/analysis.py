import discord
from discord.ext import commands


class AnalysisCog(commands.Cog):
    """Market analysis commands — economic calendar and market bias."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='calendar')
    async def calendar(self, ctx, days: int = 7, country: str = "US"):
        """Get the economic calendar. Usage: !calendar [days] [country]"""
        if days < 1 or days > 30:
            await ctx.send("Please provide a number of days between 1 and 30")
            return
        async with ctx.typing():
            events = await self.bot.get_economic_calendar(days, country)
            if not events:
                await ctx.send(f"No economic events found for {country} in the next {days} days.")
                return
            embeds = self.bot.format_economic_calendar_embed(events)
            for embed in embeds:
                await ctx.send(embed=embed)

    @commands.command(name='bias')
    async def bias(self, ctx):
        """Get the current market bias based on real index data. Usage: !bias"""
        async with ctx.typing():
            bias_data = await self.bot.get_market_bias()
            embed = self.bot.format_market_bias_embed(bias_data)
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(AnalysisCog(bot))
