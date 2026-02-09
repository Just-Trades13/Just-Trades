from discord.ext import commands
from typing import Optional, Dict, Any, List
import discord
import os
import json
import random
from typing import Optional

from src.bots.base_bot import TradingBot

class EducationBot(TradingBot):
    def __init__(self, command_prefix: str = "!", **options):
        super().__init__(command_prefix, "education_bot", **options)
        self.glossary = self._load_glossary()
        self.lessons = self._load_lessons()
        self.strategies = self._load_strategies()
        
    def _load_glossary(self) -> Dict[str, Dict[str, str]]:
        """Load trading glossary terms."""
        glossary = {
            'support': {
                'definition': 'A price level where a downtrend can be expected to pause due to a concentration of demand.',
                'example': 'If a stock has bounced off $50 multiple times, $50 is a support level.',
                'related': ['resistance', 'trendline', 'price action']
            },
            'resistance': {
                'definition': 'A price level where an uptrend can be expected to pause due to a concentration of supply.',
                'example': 'If a stock has been rejected at $100 multiple times, $100 is a resistance level.',
                'related': ['support', 'breakout', 'price action']
            },
            # Add more terms as needed
        }
        return glossary
        
    def _load_lessons(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load trading lessons."""
        lessons = {
            'beginner': [
                {
                    'title': 'Introduction to Trading',
                    'content': 'Learn the basics of trading and how financial markets work.',
                    'topics': ['Market Basics', 'Order Types', 'Risk Management'],
                    'duration': '15 min',
                    'difficulty': 'Beginner'
                },
                # Add more beginner lessons
            ],
            'intermediate': [
                {
                    'title': 'Technical Analysis Fundamentals',
                    'content': 'Learn how to read charts and use technical indicators.',
                    'topics': ['Chart Patterns', 'Indicators', 'Support/Resistance'],
                    'duration': '25 min',
                    'difficulty': 'Intermediate'
                },
                # Add more intermediate lessons
            ],
            'advanced': [
                {
                    'title': 'Advanced Options Strategies',
                    'content': 'Learn complex options strategies for advanced traders.',
                    'topics': ['Iron Condor', 'Butterfly Spread', 'Calendar Spread'],
                    'duration': '35 min',
                    'difficulty': 'Advanced'
                },
                # Add more advanced lessons
            ]
        }
        return lessons
        
    def _load_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Load trading strategies."""
        return {
            'mean_reversion': {
                'description': 'Capitalizes on the tendency of prices to revert to their mean over time.',
                'indicators': ['Bollinger Bands', 'RSI', 'Stochastic Oscillator'],
                'setup': 'Look for overbought/oversold conditions with RSI and price at Bollinger Bands',
                'entry': 'Enter when RSI crosses back below 70 (for shorts) or above 30 (for longs)',
                'exit': 'Take profit at middle Bollinger Band or when RSI reaches opposite extreme',
                'risk_management': 'Stop loss outside recent swing high/low',
                'difficulty': 'Intermediate'
            },
            'breakout': {
                'description': 'Trading the breakout of key support/resistance levels or chart patterns.',
                'indicators': ['Volume', 'Support/Resistance', 'Chart Patterns'],
                'setup': 'Identify consolidation patterns with decreasing volume',
                'entry': 'Enter on a close above resistance or below support with increased volume',
                'exit': 'Target previous support/resistance levels or use ATR-based targets',
                'risk_management': 'Stop loss just inside the breakout level',
                'difficulty': 'Beginner'
            },
            # Add more strategies
        }
    
    def get_term_embed(self, term: str) -> Optional[discord.Embed]:
        """Get a trading term's definition as an embed."""
        term_data = self.glossary.get(term.lower())
        if not term_data:
            return None
            
        embed = discord.Embed(
            title=f"📖 {term.title()}",
            description=term_data['definition'],
            color=0x9b59b6
        )
        
        if 'example' in term_data:
            embed.add_field(name="Example", value=term_data['example'], inline=False)
            
        if 'related' in term_data and term_data['related']:
            related = ", ".join([f"`{t}`" for t in term_data['related']])
            embed.add_field(name="Related Terms", value=related, inline=False)
            
        return embed
        
    def get_lesson_embed(self, level: str, lesson_index: int) -> Optional[discord.Embed]:
        """Get a lesson embed by level and index."""
        lessons = self.lessons.get(level.lower(), [])
        if not lessons or lesson_index >= len(lessons):
            return None
            
        lesson = lessons[lesson_index]
        embed = discord.Embed(
            title=f"📚 {lesson['title']}",
            description=lesson['content'],
            color=0x3498db
        )
        
        topics = "\n".join([f"• {topic}" for topic in lesson['topics']])
        embed.add_field(name="Topics Covered", value=topics, inline=False)
        
        embed.set_footer(
            text=f"Level: {lesson.get('difficulty', level).title()} | "
                 f"Duration: {lesson.get('duration', 'N/A')} | "
                 f"Lesson {lesson_index + 1} of {len(lessons)}"
        )
        
        return embed
        
    def get_strategy_embed(self, strategy_name: str) -> Optional[discord.Embed]:
        """Get a trading strategy's details as an embed."""
        strategy = self.strategies.get(strategy_name.lower())
        if not strategy:
            return None
            
        embed = discord.Embed(
            title=f"🎯 {strategy_name.title()} Strategy",
            description=strategy['description'],
            color=0xe74c3c
        )
        
        # Add strategy details
        details = [
            f"**Indicators:** {', '.join(strategy['indicators'])}",
            f"**Setup:** {strategy['setup']}",
            f"**Entry:** {strategy['entry']}",
            f"**Exit:** {strategy['exit']}",
            f"**Risk Management:** {strategy['risk_management']}",
            f"**Difficulty:** {strategy.get('difficulty', 'N/A')}"
        ]
        
        embed.add_field(
            name="Strategy Details",
            value="\n\n".join(details),
            inline=False
        )
        
        return embed

# Command line entry point
def main():
    """Run the Education Bot."""
    bot = EducationBot()
    
    @bot.command(name='term')
    async def term(ctx, *, term_name: str):
        """Look up a trading term in the glossary."""
        embed = bot.get_term_embed(term_name)
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Could not find term: {term_name}")
    
    @bot.command(name='lesson')
    async def lesson(ctx, level: str = 'beginner', lesson_num: int = 1):
        """Get a trading lesson."""
        level = level.lower()
        if level not in ['beginner', 'intermediate', 'advanced']:
            await ctx.send("❌ Please choose a valid level: beginner, intermediate, or advanced")
            return
            
        embed = bot.get_lesson_embed(level, lesson_num - 1)  # Convert to 0-based index
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Could not find lesson {lesson_num} for level {level}")
    
    @bot.command(name='strategy')
    async def strategy(ctx, strategy_name: str):
        """Get details about a trading strategy."""
        embed = bot.get_strategy_embed(strategy_name)
        if embed:
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"❌ Could not find strategy: {strategy_name}")
    
    bot.run()

if __name__ == "__main__":
    main()
