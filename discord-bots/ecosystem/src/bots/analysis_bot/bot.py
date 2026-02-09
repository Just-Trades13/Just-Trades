from discord.ext import commands
from typing import Optional, Dict, Any, List
import discord
import os
import aiohttp
import pytz
from datetime import datetime, timedelta

from src.bots.base_bot import TradingBot


class AnalysisBot(TradingBot):
    def __init__(self, command_prefix: str = "!", **options):
        super().__init__(command_prefix, "analysis_bot", **options)
        self.session: Optional[aiohttp.ClientSession] = None
        self.timezone = pytz.timezone(os.getenv('TIMEZONE', 'America/Chicago'))

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
        """Get economic calendar events from Financial Modeling Prep API."""
        try:
            api_key = os.getenv('FINANCIAL_DATA_API_KEY')
            if not api_key:
                self.logger.warning("FINANCIAL_DATA_API_KEY not set")
                return []

            from_date = datetime.now().strftime('%Y-%m-%d')
            to_date = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

            url = "https://financialmodelingprep.com/api/v3/economic_calendar"
            params = {
                'from': from_date,
                'to': to_date,
                'apikey': api_key
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    self.logger.warning(f"Economic calendar API returned {response.status}")
                    return []
                data = await response.json()

            # Filter by country and sort by date
            events = [
                event for event in data
                if event.get('country', '').upper() == country.upper()
            ]
            events.sort(key=lambda x: x.get('date', ''))
            return events

        except Exception as e:
            self.logger.error(f"Error fetching economic calendar: {e}")
            return []

    def format_economic_calendar_embed(self, events: List[Dict[str, Any]]) -> List[discord.Embed]:
        """Format economic calendar events into Discord embeds."""
        if not events:
            return []

        # Group events by date
        events_by_date = {}
        for event in events:
            event_date = event.get('date', '')[:10]
            if event_date not in events_by_date:
                events_by_date[event_date] = []
            events_by_date[event_date].append(event)

        embeds = []
        for date, date_events in events_by_date.items():
            date_events.sort(key=lambda x: x.get('date', ''))

            embed = discord.Embed(
                title=f"📅 Economic Calendar — {date}",
                color=0x3498db
            )

            for event in date_events[:10]:
                event_time = event.get('date', '')[11:16] or 'TBD'
                impact = event.get('impact', '').lower()

                impact_indicator = '🔴' if impact == 'high' else '🟡' if impact == 'medium' else '🟢'

                prev_val = event.get('previous', 'N/A')
                forecast_val = event.get('estimate', event.get('forecast', 'N/A'))
                actual_val = event.get('actual', '')

                value_parts = [f"Impact: {impact_indicator} {impact.title()}"]
                if prev_val and prev_val != 'N/A':
                    value_parts.append(f"Previous: {prev_val}")
                if forecast_val and forecast_val != 'N/A':
                    value_parts.append(f"Forecast: {forecast_val}")
                if actual_val:
                    value_parts.append(f"**Actual: {actual_val}**")

                embed.add_field(
                    name=f"{event_time} — {event.get('event', 'Unknown Event')}",
                    value="\n".join(value_parts),
                    inline=False
                )

            embeds.append(embed)

        return embeds

    async def get_market_bias(self) -> Dict[str, Any]:
        """Get current market bias by fetching real index data from Yahoo Finance."""
        try:
            symbols = {
                'SPY': 'S&P 500',
                'QQQ': 'Nasdaq 100',
                'DIA': 'Dow Jones',
                'IWM': 'Russell 2000',
            }

            results = {}
            for symbol, name in symbols.items():
                url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5d"
                headers = {"User-Agent": "Mozilla/5.0"}
                try:
                    async with self.session.get(url, headers=headers) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            chart_result = data.get('chart', {}).get('result', [])
                            if chart_result:
                                closes = chart_result[0].get('indicators', {}).get('quote', [{}])[0].get('close', [])
                                if len(closes) >= 2:
                                    current = closes[-1]
                                    prev = closes[-2]
                                    if current and prev:
                                        results[name] = {
                                            'price': current,
                                            'change_pct': ((current - prev) / prev * 100)
                                        }
                except Exception:
                    continue

            if not results:
                return {
                    'bias': 'Unavailable',
                    'reason': 'Could not fetch market data. Check API connectivity.',
                    'markets': {},
                    'timestamp': datetime.now(pytz.UTC)
                }

            # Calculate overall bias from equity indices
            equity_changes = [data['change_pct'] for data in results.values()]
            avg_change = sum(equity_changes) / len(equity_changes) if equity_changes else 0

            if avg_change > 0.5:
                bias = 'Bullish'
                reason = 'Broad market strength across major indices.'
            elif avg_change > 0:
                bias = 'Mildly Bullish'
                reason = 'Slight upward momentum, no strong conviction.'
            elif avg_change > -0.5:
                bias = 'Mildly Bearish'
                reason = 'Slight weakness, watching for follow-through.'
            else:
                bias = 'Bearish'
                reason = 'Broad market weakness across major indices.'

            return {
                'bias': bias,
                'reason': reason,
                'avg_change': avg_change,
                'markets': results,
                'timestamp': datetime.now(pytz.UTC)
            }

        except Exception as e:
            self.logger.error(f"Error getting market bias: {e}")
            return {
                'bias': 'Error',
                'reason': f'Failed to fetch data: {str(e)}',
                'markets': {},
                'timestamp': datetime.now(pytz.UTC)
            }

    def format_market_bias_embed(self, bias_data: Dict[str, Any]) -> discord.Embed:
        """Format market bias into a Discord embed."""
        bias = bias_data['bias']
        if 'Bullish' in bias:
            color = 0x00ff00
        elif 'Bearish' in bias:
            color = 0xff0000
        else:
            color = 0x808080

        embed = discord.Embed(
            title=f"📊 Market Bias: {bias}",
            color=color,
            description=bias_data['reason'],
            timestamp=bias_data['timestamp']
        )

        # Add each market with real data
        markets = bias_data.get('markets', {})
        for name, data in markets.items():
            change = data['change_pct']
            indicator = '📈' if change >= 0 else '📉'
            embed.add_field(
                name=f"{indicator} {name}",
                value=f"${data['price']:,.2f} ({change:+.2f}%)",
                inline=True
            )

        embed.set_footer(text="Just Trades Analysis | Data from Yahoo Finance")
        return embed


# Command line entry point
def main():
    """Run the Analysis Bot standalone."""
    bot = AnalysisBot()

    @bot.command(name='calendar')
    async def calendar(ctx, days: int = 7, country: str = "US"):
        """Get the economic calendar. Usage: !calendar [days] [country]"""
        if days < 1 or days > 30:
            await ctx.send("Please provide a number of days between 1 and 30")
            return
        async with ctx.typing():
            events = await bot.get_economic_calendar(days, country)
            if not events:
                await ctx.send(f"No economic events found for {country} in the next {days} days.")
                return
            embeds = bot.format_economic_calendar_embed(events)
            for embed in embeds:
                await ctx.send(embed=embed)

    @bot.command(name='bias')
    async def bias(ctx):
        """Get the current market bias. Usage: !bias"""
        async with ctx.typing():
            bias_data = await bot.get_market_bias()
            embed = bot.format_market_bias_embed(bias_data)
            await ctx.send(embed=embed)

    bot.run()

if __name__ == "__main__":
    main()
