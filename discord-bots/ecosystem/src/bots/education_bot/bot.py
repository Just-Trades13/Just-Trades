from discord.ext import commands
from typing import Optional, Dict, Any, List
import discord
import os

from src.bots.base_bot import TradingBot


class EducationBot(TradingBot):
    def __init__(self, command_prefix: str = "!", **options):
        super().__init__(command_prefix, "education_bot", **options)
        self.glossary = self._load_glossary()
        self.lessons = self._load_lessons()
        self.strategies = self._load_strategies()

    def _load_glossary(self) -> Dict[str, Dict[str, str]]:
        """Load trading glossary terms."""
        return {
            'support': {
                'definition': 'A price level where a downtrend can be expected to pause due to a concentration of demand. Buyers step in at this level, preventing the price from falling further.',
                'example': 'If NQ has bounced off 20,000 three times in a week, 20,000 is acting as support.',
                'related': ['resistance', 'trendline', 'price action']
            },
            'resistance': {
                'definition': 'A price level where an uptrend can be expected to pause due to a concentration of supply. Sellers step in at this level, preventing the price from rising further.',
                'example': 'If ES keeps getting rejected at 5,200, that level is resistance.',
                'related': ['support', 'breakout', 'price action']
            },
            'breakout': {
                'definition': 'When price moves above a resistance level or below a support level with conviction (usually confirmed by volume). Breakouts often signal the start of a new trend.',
                'example': 'NQ consolidating between 20,000-20,200 then pushing above 20,200 on heavy volume is a bullish breakout.',
                'related': ['support', 'resistance', 'volume', 'fakeout']
            },
            'fakeout': {
                'definition': 'A false breakout where price briefly moves beyond support/resistance but quickly reverses back. Designed to trap traders who entered on the breakout.',
                'example': 'Price pushes above resistance, triggers buy stops, then immediately sells off below the level.',
                'related': ['breakout', 'stop hunt', 'liquidity']
            },
            'liquidity': {
                'definition': 'The ease with which an asset can be bought or sold without significantly affecting its price. In trading, liquidity pools are clusters of stop-loss orders that smart money targets.',
                'example': 'Stop losses sitting below a swing low represent sell-side liquidity that institutions may sweep before going long.',
                'related': ['stop hunt', 'order flow', 'smart money']
            },
            'order flow': {
                'definition': 'The study of actual buy and sell orders hitting the market. Shows the real-time battle between buyers and sellers at specific price levels.',
                'example': 'Seeing aggressive market buy orders absorbing limit sell orders at a resistance level suggests the level will break.',
                'related': ['volume', 'order book', 'delta']
            },
            'delta': {
                'definition': 'The difference between buying volume and selling volume at a price level. Positive delta means more aggressive buying; negative delta means more aggressive selling.',
                'example': 'A candle with +5000 delta means 5000 more contracts were bought at the ask than sold at the bid.',
                'related': ['order flow', 'volume', 'cumulative delta']
            },
            'dca': {
                'definition': 'Dollar Cost Averaging — adding to an existing position at a different price to improve the average entry price. In futures, this means adding contracts as price moves against you.',
                'example': 'Long 1 NQ at 20,100, price drops to 20,050, add 1 more. New average entry: 20,075.',
                'related': ['position sizing', 'risk management', 'averaging down']
            },
            'take profit': {
                'definition': 'A limit order placed at a target price to automatically close a position for profit. Also called TP. Can be set as ticks, points, or percentage from entry.',
                'example': 'Entry at 20,000 with a 40-tick TP on NQ = take profit at 20,010 (each NQ tick = 0.25 points).',
                'related': ['stop loss', 'risk reward', 'bracket order']
            },
            'stop loss': {
                'definition': 'An order placed to limit losses by automatically closing a position when price reaches a specified level. Essential for risk management.',
                'example': 'Long NQ at 20,000 with a 20-point stop loss = stop at 19,980. Max loss = $400 per contract.',
                'related': ['take profit', 'risk management', 'trailing stop']
            },
            'trailing stop': {
                'definition': 'A stop loss that automatically moves in your favor as the trade moves in profit. Locks in gains while still giving the trade room to run.',
                'example': 'Trail trigger at 20 ticks, trail freq at 5 ticks: once 20 ticks in profit, the stop trails every 5 ticks of favorable movement.',
                'related': ['stop loss', 'break even', 'risk management']
            },
            'break even': {
                'definition': 'Moving your stop loss to your entry price after the trade moves a certain distance in your favor. Eliminates risk on the trade.',
                'example': 'Entry at 20,000, break-even trigger at 15 ticks: once price hits 20,003.75, stop moves to 20,000.',
                'related': ['stop loss', 'trailing stop', 'risk management']
            },
            'bracket order': {
                'definition': 'An order that includes an entry, a take profit, and a stop loss all in one submission. The TP and SL are OCO (one cancels other) — when one fills, the other is cancelled.',
                'example': 'Buy 1 NQ at market with TP at +40 ticks and SL at -20 ticks, all in one order.',
                'related': ['take profit', 'stop loss', 'oco']
            },
            'scalping': {
                'definition': 'A trading style focused on making many small profits from tiny price movements. Scalpers hold positions for seconds to minutes.',
                'example': 'Entering NQ for 8-12 ticks of profit, multiple times per session, with tight stop losses.',
                'related': ['day trading', 'swing trading', 'order flow']
            },
            'swing trading': {
                'definition': 'A trading style that holds positions for days to weeks, aiming to capture larger price moves. Uses higher timeframe analysis.',
                'example': 'Going long ES on a daily chart pullback to the 20 EMA, targeting the next resistance level over 3-5 days.',
                'related': ['day trading', 'scalping', 'position trading']
            },
            'risk reward': {
                'definition': 'The ratio of potential loss to potential profit on a trade. A 1:3 R:R means risking $1 to make $3. Higher ratios allow lower win rates to be profitable.',
                'example': 'Risking 10 ticks to make 30 ticks = 1:3 risk/reward. You only need to win 25%+ of trades to be profitable.',
                'related': ['take profit', 'stop loss', 'position sizing']
            },
            'position sizing': {
                'definition': 'Determining how many contracts/shares to trade based on your account size and risk tolerance. The foundation of risk management.',
                'example': '$50K account risking 1% per trade = $500 max risk. At 20 ticks SL on NQ ($100/tick), trade 5 contracts max.',
                'related': ['risk management', 'risk reward', 'leverage']
            },
            'volume': {
                'definition': 'The number of shares or contracts traded during a given period. Volume confirms price moves — high volume breakouts are more reliable than low volume ones.',
                'example': 'NQ breaks above resistance on 2x average volume = strong breakout. Same break on low volume = likely fakeout.',
                'related': ['order flow', 'delta', 'liquidity']
            },
            'ema': {
                'definition': 'Exponential Moving Average — a moving average that gives more weight to recent prices. Common EMAs: 9, 20, 50, 200. Used to identify trends and dynamic support/resistance.',
                'example': 'Price above the 200 EMA = bullish trend. Price below = bearish. The 9 EMA often acts as dynamic support in strong trends.',
                'related': ['sma', 'trend', 'moving average']
            },
            'vwap': {
                'definition': 'Volume Weighted Average Price — the average price weighted by volume for the trading session. Institutional benchmark. Price above VWAP = bullish bias, below = bearish.',
                'example': 'NQ above VWAP at 20,050 with VWAP rising = bullish day. Look for longs on pullbacks to VWAP.',
                'related': ['ema', 'volume', 'institutional trading']
            },
        }

    def _load_lessons(self) -> Dict[str, List[Dict[str, Any]]]:
        """Load trading lessons."""
        return {
            'beginner': [
                {
                    'title': 'Introduction to Futures Trading',
                    'content': 'Futures are standardized contracts to buy/sell an asset at a predetermined price on a future date. Unlike stocks, futures use leverage — you control a large position with a small margin deposit.\n\n**Key concepts:**\n- **Margin**: The deposit required (e.g., $500 for 1 MNQ contract worth ~$40,000)\n- **Tick**: The minimum price increment (MNQ = 0.25 points = $0.50)\n- **Point**: A full point movement (MNQ 1 point = $2.00)\n- **Contract**: One unit of the futures instrument',
                    'topics': ['What are futures?', 'Margin and leverage', 'Ticks vs points vs dollars', 'Contract specifications'],
                    'duration': '15 min',
                    'difficulty': 'Beginner'
                },
                {
                    'title': 'Order Types Explained',
                    'content': '**Market Order**: Buy/sell immediately at the current best price. Fast but no price control.\n\n**Limit Order**: Buy/sell at a specific price or better. You control the price but it may not fill.\n\n**Stop Order**: Becomes a market order when price reaches your stop price. Used for stop losses.\n\n**Stop Limit**: Becomes a limit order when triggered. More price control than a stop but may not fill in fast markets.\n\n**Bracket Order**: Entry + TP + SL all in one. The TP and SL are OCO (one cancels other).',
                    'topics': ['Market orders', 'Limit orders', 'Stop orders', 'Bracket orders', 'OCO orders'],
                    'duration': '10 min',
                    'difficulty': 'Beginner'
                },
                {
                    'title': 'Risk Management Basics',
                    'content': 'Risk management is THE most important skill in trading. Without it, even the best strategy will blow your account.\n\n**Rules:**\n1. Never risk more than 1-2% of your account on a single trade\n2. Always use a stop loss — no exceptions\n3. Define your risk BEFORE entering the trade\n4. Position size based on your stop distance, not your conviction\n5. Set a max daily loss and stop trading when you hit it\n\n**Formula**: Position Size = (Account Risk $) / (Stop Loss $ per contract)',
                    'topics': ['The 1-2% rule', 'Stop loss placement', 'Position sizing formula', 'Max daily loss', 'Trading psychology'],
                    'duration': '20 min',
                    'difficulty': 'Beginner'
                },
            ],
            'intermediate': [
                {
                    'title': 'Technical Analysis Fundamentals',
                    'content': 'Technical analysis studies price charts and indicators to predict future price movements.\n\n**Core principles:**\n- Price discounts everything (news, fundamentals are reflected in price)\n- Price moves in trends (up, down, or sideways)\n- History tends to repeat (patterns recur because human psychology is consistent)\n\n**Key tools:** Support/resistance, trendlines, moving averages (EMA 9/20/50/200), VWAP, RSI, volume analysis.',
                    'topics': ['Chart reading basics', 'Support and resistance', 'Trend identification', 'Key indicators (EMA, VWAP, RSI)'],
                    'duration': '25 min',
                    'difficulty': 'Intermediate'
                },
                {
                    'title': 'Chart Patterns That Work',
                    'content': '**Continuation patterns** (trend continues):\n- Bull/bear flags: Sharp move followed by tight consolidation\n- Triangles: Converging trendlines showing compression\n- Channels: Parallel trendlines price bounces between\n\n**Reversal patterns** (trend changes):\n- Double top/bottom: Two tests of a level that holds\n- Head and shoulders: Three peaks with the middle highest\n- Failed breakout: Price breaks a level then reverses hard\n\nVolume confirms patterns — look for volume expansion on the breakout.',
                    'topics': ['Bull and bear flags', 'Triangles and wedges', 'Double tops and bottoms', 'Head and shoulders', 'Volume confirmation'],
                    'duration': '30 min',
                    'difficulty': 'Intermediate'
                },
                {
                    'title': 'DCA and Position Management',
                    'content': 'Dollar Cost Averaging (DCA) in futures means adding to your position at better prices to improve your average entry.\n\n**When DCA makes sense:**\n- You have a valid setup with a defined max risk\n- The pullback is within your expected range\n- You pre-plan your DCA levels before entering\n\n**DCA math example:**\n- Long 1 NQ @ 20,100\n- Add 1 NQ @ 20,050 (DCA)\n- New avg entry: 20,075\n- TP recalculated from new average\n\n**Danger:** DCA without a plan = averaging into a losing trade. Always have a max position size and a hard stop.',
                    'topics': ['When to DCA', 'DCA math and averaging', 'Position size limits', 'TP recalculation after DCA', 'When NOT to DCA'],
                    'duration': '20 min',
                    'difficulty': 'Intermediate'
                },
            ],
            'advanced': [
                {
                    'title': 'Order Flow and Market Microstructure',
                    'content': 'Order flow analysis looks at the actual orders hitting the market rather than just the resulting candles.\n\n**Key concepts:**\n- **Bid/Ask**: Bid = buyers waiting, Ask = sellers waiting\n- **Delta**: Buy volume minus sell volume at a price\n- **Cumulative Delta**: Running total of delta for the session\n- **Absorption**: Large limit orders absorbing aggressive market orders\n- **Imbalance**: Significant delta at a price level\n\nOrder flow shows you WHO is in control. A rising price with negative delta suggests buyers are getting exhausted.',
                    'topics': ['Bid/Ask dynamics', 'Delta and cumulative delta', 'Absorption and imbalance', 'Footprint charts', 'Institutional order flow'],
                    'duration': '35 min',
                    'difficulty': 'Advanced'
                },
                {
                    'title': 'Multi-Timeframe Analysis',
                    'content': 'Using multiple timeframes to align your trades with the bigger picture.\n\n**Framework:**\n1. **Higher TF (Daily/4H)**: Identify the trend and key levels\n2. **Trading TF (15m/5m)**: Find your setup and entry\n3. **Entry TF (1m/Tick)**: Time your entry precisely\n\n**Rules:**\n- Never trade against the higher timeframe trend\n- Use higher TF levels as your TP targets\n- The lower TF entry should align with higher TF direction\n- If higher TF is choppy/ranging, reduce size or sit out',
                    'topics': ['Timeframe hierarchy', 'Top-down analysis', 'Entry timing', 'Conflicting signals between timeframes'],
                    'duration': '25 min',
                    'difficulty': 'Advanced'
                },
                {
                    'title': 'Trading Psychology and Discipline',
                    'content': 'The market is designed to exploit your emotions. Mastering psychology separates profitable traders from the rest.\n\n**Common traps:**\n- **Revenge trading**: Taking impulsive trades after a loss\n- **FOMO**: Chasing a move you missed\n- **Overtrading**: Trading out of boredom, not conviction\n- **Moving stops**: Widening your stop "just a little"\n\n**Solutions:**\n- Pre-define your setup and ONLY take those setups\n- Set a max daily loss and STOP when you hit it\n- Journal every trade — review weekly\n- Accept that losses are part of the business',
                    'topics': ['Revenge trading', 'FOMO', 'Overtrading', 'The importance of journaling', 'Building a routine'],
                    'duration': '20 min',
                    'difficulty': 'Advanced'
                },
            ]
        }

    def _load_strategies(self) -> Dict[str, Dict[str, Any]]:
        """Load trading strategies."""
        return {
            'breakout': {
                'description': 'Trading the breakout of key support/resistance levels or consolidation patterns. Works best when the market has been compressing (narrowing range) before the break.',
                'indicators': ['Volume', 'Support/Resistance', 'ATR', 'VWAP'],
                'setup': 'Identify a clear consolidation zone with decreasing volume. Wait for a decisive close beyond the range boundary.',
                'entry': 'Enter on a close above resistance (longs) or below support (shorts) with volume at least 1.5x average.',
                'exit': 'Target the measured move (height of the range projected from the breakout). Trail stop to breakeven after 1:1.',
                'risk_management': 'Stop loss just inside the breakout level (e.g., 2 ticks inside the range). Risk 1% max.',
                'difficulty': 'Beginner'
            },
            'mean_reversion': {
                'description': 'Capitalizes on the tendency of prices to revert to their mean (VWAP, EMA) after overextended moves. Best in ranging/choppy markets.',
                'indicators': ['Bollinger Bands', 'RSI', 'VWAP', 'Stochastic'],
                'setup': 'Look for price extended 2+ standard deviations from VWAP with RSI > 70 (overbought) or < 30 (oversold).',
                'entry': 'Enter when RSI crosses back below 70 (shorts) or above 30 (longs). Confirm with a rejection candle.',
                'exit': 'Take profit at VWAP or the 20 EMA. This is a short-term play — don\'t hold for big moves.',
                'risk_management': 'Stop loss beyond the swing high/low that formed the extreme. Tight stops, quick targets.',
                'difficulty': 'Intermediate'
            },
            'trend_following': {
                'description': 'Trading in the direction of the established trend using pullbacks as entry points. "The trend is your friend until it ends."',
                'indicators': ['EMA 9/20/50', 'VWAP', 'Higher highs/higher lows'],
                'setup': 'Confirm uptrend: price above rising 20 EMA, making higher highs and higher lows. Wait for a pullback to the 9 or 20 EMA.',
                'entry': 'Enter long when price bounces off the 20 EMA with a bullish candle. Enter short on rejection of falling 20 EMA.',
                'exit': 'Target previous swing high (longs) or swing low (shorts). Trail stop below the prior pullback low.',
                'risk_management': 'Stop below the pullback low (longs) or above pullback high (shorts). Only trade WITH the trend.',
                'difficulty': 'Beginner'
            },
            'vwap_bounce': {
                'description': 'Trading bounces off VWAP (Volume Weighted Average Price), the institutional benchmark price. Price tends to revisit VWAP and either bounce or break through.',
                'indicators': ['VWAP', 'Volume', 'EMA 9'],
                'setup': 'Price pulls back to VWAP from above (bullish) or below (bearish). Look for a hold/bounce at VWAP with a reaction candle.',
                'entry': 'Enter on a 1-minute candle that closes back above VWAP (longs) after testing it. Volume should pick up on the bounce.',
                'exit': 'Target previous session high/low or the next major level. First target at 1:1 R:R.',
                'risk_management': 'Stop 2-3 points below VWAP (longs) or above (shorts). If VWAP breaks cleanly, the setup is invalid.',
                'difficulty': 'Intermediate'
            },
            'opening_range': {
                'description': 'Trading the breakout of the first 15-30 minutes of the trading session. The opening range establishes the initial balance for the day.',
                'indicators': ['Opening range high/low', 'Volume', 'VWAP'],
                'setup': 'Mark the high and low of the first 15 or 30 minutes. Wait for a break above or below with volume confirmation.',
                'entry': 'Enter on a close above the opening range high (longs) or below the low (shorts). Stronger if VWAP aligns.',
                'exit': 'Target 1x the opening range height projected from the breakout. Many traders target yesterday\'s high/low.',
                'risk_management': 'Stop at the midpoint of the opening range. Risk 1% of account max.',
                'difficulty': 'Beginner'
            },
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
        if not lessons or lesson_index < 0 or lesson_index >= len(lessons):
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
        # Allow both "mean_reversion" and "mean reversion"
        key = strategy_name.lower().replace(' ', '_')
        strategy = self.strategies.get(key)
        if not strategy:
            return None

        embed = discord.Embed(
            title=f"🎯 {strategy_name.replace('_', ' ').title()} Strategy",
            description=strategy['description'],
            color=0xe74c3c
        )

        embed.add_field(name="Indicators", value=', '.join(strategy['indicators']), inline=False)
        embed.add_field(name="Setup", value=strategy['setup'], inline=False)
        embed.add_field(name="Entry", value=strategy['entry'], inline=False)
        embed.add_field(name="Exit", value=strategy['exit'], inline=False)
        embed.add_field(name="Risk Management", value=strategy['risk_management'], inline=False)
        embed.add_field(name="Difficulty", value=strategy.get('difficulty', 'N/A'), inline=True)

        return embed


# Command line entry point
def main():
    """Run the Education Bot standalone."""
    bot = EducationBot()
    bot.run()

if __name__ == "__main__":
    main()
