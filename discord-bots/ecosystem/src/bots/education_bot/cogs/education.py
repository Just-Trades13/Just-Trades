import discord
from discord.ext import commands
from typing import Optional


class EducationCog(commands.Cog):
    """Trading education commands — glossary, lessons, strategies."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='term')
    async def term(self, ctx, *, term_name: str):
        """Look up a trading term. Usage: !term support"""
        embed = self.bot.get_term_embed(term_name)
        if embed:
            await ctx.send(embed=embed)
        else:
            available = ", ".join(sorted(self.bot.glossary.keys())[:20])
            await ctx.send(f"Could not find term: **{term_name}**\n\nAvailable terms: {available}")

    @commands.command(name='lesson')
    async def lesson(self, ctx, level: str = 'beginner', lesson_num: int = 1):
        """Get a trading lesson. Usage: !lesson beginner 1"""
        level = level.lower()
        if level not in ['beginner', 'intermediate', 'advanced']:
            await ctx.send("Please choose a valid level: beginner, intermediate, or advanced")
            return
        embed = self.bot.get_lesson_embed(level, lesson_num - 1)
        if embed:
            await ctx.send(embed=embed)
        else:
            count = len(self.bot.lessons.get(level, []))
            await ctx.send(f"Could not find lesson {lesson_num} for level {level}. Available: 1-{count}")

    @commands.command(name='strategy')
    async def strategy(self, ctx, *, strategy_name: str):
        """Get details about a trading strategy. Usage: !strategy breakout"""
        embed = self.bot.get_strategy_embed(strategy_name)
        if embed:
            await ctx.send(embed=embed)
        else:
            available = ", ".join(sorted(self.bot.strategies.keys()))
            await ctx.send(f"Could not find strategy: **{strategy_name}**\n\nAvailable: {available}")

    @commands.command(name='glossary')
    async def glossary(self, ctx):
        """List all available trading terms."""
        terms = sorted(self.bot.glossary.keys())
        embed = discord.Embed(
            title="Trading Glossary",
            description="Use `!term <name>` to look up any term.\n\n" + ", ".join([f"`{t}`" for t in terms]),
            color=0x9b59b6
        )
        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(EducationCog(bot))
