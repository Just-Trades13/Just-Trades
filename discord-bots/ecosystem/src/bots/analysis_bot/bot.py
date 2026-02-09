from discord.ext import commands
from typing import Optional, Dict, Any, List
import discord
import os
import aiohttp
import pytz
from datetime import datetime, timedelta
import pandas as pd
import json

from src.bots.base_bot import TradingBot

class AnalysisBot(TradingBot):
    def __init__(self, command_prefix: str = "!", **options):
        super().__init__(command_prefix, "analysis_bot", **options)
        self.session: Optional[aiohttp.ClientSession] = None
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'UTC'))
        
    async def setup_hook(self) -> None:
        """Setup tasks before bot connects."""
        await super().setup_hook()
        self.session = aiohttp.ClientSession()
        self.logger.info("Analysis Bot setup complete")
        
    async def close(self) -> None:
        """Clean up resources."""
        if self.session:
            await self.session.close()
        await super().close()
    
    async def get_economic_calendar(self, days: int = 7, country: str = "US") -> List[Dict[str, Any]]:
        """Get economic calendar events."""
        try:
            # Using Financial Modeling Prep API
            api_key = os.getenv('FINANCIAL_DATA_API_KEY')
            if not api_key:
                self.logger.warning("FINANCIAL_DATA_API_KEY not set")
                return []
                
            to_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            
            url = f"https://financialmodelingprep.com/api/v3/economic_calendar"
            params = {
                'from': datetime.now().strftime('%Y-%m-%d'),
                'to': to_date,
                'apikey': api_key
            }
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                
            # Filter by country and sort by date
            events = [
                event for event in data 
                if event.get('country', '').lower() == country.lower()
            ]
            
            # Sort by date
            events.sort(key=lambda x: x.get('date', ''))
            
            return events
            
        except Exception as e:
            self.logger.error(f"Error fetching economic calendar: {e}")
            return []
    
    def format_economic_calendar_embed(self, events: List[Dict[str, Any]], days: int = 1) -> List[discord.Embed]:
        """Format economic calendar events into Discord embeds."""
        if not events:
            return []
            
        # Group events by date
        events_by_date = {}
        for event in events:
            event_date = event.get('date', '')[:10]  # YYYY-MM-DD
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)
        
        embeds = []
        for date, date_events in events_by_date.items():
            # Sort events by time
            date_events.sort(key=lambda x: x.get('time', ''))
            
            # Create embed for this date
            embed = discord.Embed(
                title=f"📅 Economic Calendar - {date}",
                color=0x3498db,
                description=f"Economic events for {date}"
            )
            
            for event in date_events:
                event_time = event.get('time', 'TBD')
                impact = event.get('impact', '').lower()
                
                # Set color based on impact
                if impact == 'high':
                    color = 0xff0000  # Red
                elif impact == 'medium':
                    color = 0xffa500  # Orange
                else:
                    color = 0x00ff00  # Green
                
                # Add field for each event
                embed.add_field(
                    name=f"{event_time} - {event.get('event', 'Event')}",
                    value=(
                        f"**Country:** {event.get('country', 'N/A')}\n"
                        f"**Importance:** {impact.title()}\n"
                        f"**Previous:** {event.get('previous', 'N/A')}\n"
                        f"**Forecast:** {event.get('forecast', 'N/A')}"
                    ),
                    inline=False
                )
            
            embeds.append(embed)
        
        return embeds
    
    async def get_market_bias(self) -> Dict[str, Any]:
        """Get current market bias."""
        # This is a simplified example - in a real bot, you'd use actual market data
        return {
            'bias': 'Bullish',  # or 'Bearish' or 'Neutral'
            'reason': 'Strong earnings and positive economic data',
            'key_levels': {
                'support': ['S&P 500: 4,200', 'Nasdaq: 12,500'],
                'resistance': ['S&P 500: 4,400', 'Nasdaq: 13,000']
            },
            'timestamp': datetime.now(pytz.UTC)
        }
    
    def format_market_bias_embed(self, bias_data: Dict[str, Any]) -> discord.Embed:
        """Format market bias into a Discord embed."""
        color = 0x00ff00 if bias_data['bias'].lower() == 'bullish' else 0xff0000
        
        embed = discord.Embed(
            title=f"📊 Market Bias: {bias_data['bias']}",
            color=color,
            description=bias_data['reason'],
            timestamp=bias_data['timestamp']
        )
        
        # Add support and resistance levels
        embed.add_field(
            name="🔽 Key Support Levels",
            value="\n".join([f"• {level}" for level in bias_data['key_levels']['support']]),
            inline=True
        )
        
        embed.add_field(
            name="🔼 Key Resistance Levels",
            value="\n".join([f"• {level}" for level in bias_data['key_levels']['resistance']]),
            inline=True
        )
        
        return embed

# Command line entry point
def main():
    """Run the Analysis Bot."""
    bot = AnalysisBot()
    
    @bot.command(name='calendar')
    async def calendar(ctx, days: int = 7, country: str = "US"):
        """Get the economic calendar for the specified number of days."""
        if days < 1 or days > 30:
            await ctx.send("Please provide a number of days between 1 and 30")
            return
            
        async with ctx.typing():
            events = await bot.get_economic_calendar(days, country)
            if not events:
                await ctx.send(f"❌ No economic events found for {country}")
                return
                
            embeds = bot.format_economic_calendar_embed(events, days)
            for embed in embeds:
                await ctx.send(embed=embed)
    
    @bot.command(name='bias')
    async def bias(ctx):
        """Get the current market bias."""
        async with ctx.typing():
            bias_data = await bot.get_market_bias()
            embed = bot.format_market_bias_embed(bias_data)
            await ctx.send(embed=embed)
    
    bot.run()

if __name__ == "__main__":
    main()
