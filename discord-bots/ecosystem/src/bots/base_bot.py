import discord
from discord.ext import commands
import logging
import os
from dotenv import load_dotenv
from typing import Optional, Dict, Any

load_dotenv()

class TradingBot(commands.Bot):
    def __init__(self, command_prefix: str, bot_type: str, **options):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        
        super().__init__(command_prefix, intents=intents, **options)
        self.bot_type = bot_type
        self.logger = self._setup_logging()
        self.channels: Dict[str, Optional[discord.TextChannel]] = {}
        
    def _setup_logging(self) -> logging.Logger:
        """Configure logging for the bot."""
        logger = logging.getLogger(f"trading_bot.{self.bot_type}")
        logger.setLevel(logging.INFO)
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # File handler
        file_handler = logging.FileHandler(f'logs/{self.bot_type}.log')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
        
    async def setup_hook(self) -> None:
        """Setup tasks before bot connects."""
        self.logger.info("Setting up bot...")
        await self.load_extensions()
        await self.cache_channels()
        
    async def load_extensions(self) -> None:
        """Load all extensions (cogs) for the bot."""
        try:
            # Load all Python files in the cogs directory
            for filename in os.listdir(f"src/bots/{self.bot_type}/cogs"):
                if filename.endswith('.py') and not filename.startswith('_'):
                    cog_name = f"src.bots.{self.bot_type}.cogs.{filename[:-3]}"
                    try:
                        await self.load_extension(cog_name)
                        self.logger.info(f"Loaded extension: {cog_name}")
                    except Exception as e:
                        self.logger.error(f"Failed to load extension {cog_name}: {e}")
        except FileNotFoundError:
            self.logger.warning(f"No cogs directory found for {self.bot_type}")
        
    async def cache_channels(self) -> None:
        """Cache frequently accessed channels."""
        guild = self.get_guild(int(os.getenv('GUILD_ID', '0')))
        if not guild:
            self.logger.error("Guild not found")
            return
            
        self.channels = {
            'news': guild.get_channel(int(os.getenv('CHANNEL_NEWS', '0'))),
            'financial_juice': guild.get_channel(int(os.getenv('CHANNEL_FINANCIAL_JUICE', '0'))),
            'economic_calendar': guild.get_channel(int(os.getenv('CHANNEL_ECONOMIC_CALENDAR', '0'))),
            'daily_bias': guild.get_channel(int(os.getenv('CHANNEL_DAILY_BIAS', '0'))),
            'education_hub': guild.get_channel(int(os.getenv('CHANNEL_EDUCATION_HUB', '0'))),
            'trading_glossary': guild.get_channel(int(os.getenv('CHANNEL_TRADING_GLOSSARY', '0'))),
            'chart_setups': guild.get_channel(int(os.getenv('CHANNEL_CHART_SETUPS', '0'))),
            'advanced_strategies': guild.get_channel(int(os.getenv('CHANNEL_ADVANCED_STRATEGIES', '0')))
        }
        
        # Log channel status
        for name, channel in self.channels.items():
            if channel:
                self.logger.info(f"Cached channel: {name} ({channel.id})")
            else:
                self.logger.warning(f"Failed to cache channel: {name}")
        
    async def on_ready(self) -> None:
        """Called when the bot is ready."""
        self.logger.info(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="the markets 📈"
            )
        )
        self.logger.info("Bot is ready and online!")
        
    async def on_command_error(self, ctx, error):
        """Global error handler for commands."""
        if isinstance(error, commands.CommandNotFound):
            return
            
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param.name}")
            return
            
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Bad argument: {error}")
            return
            
        # Log the error
        self.logger.error(f"Command error: {error}", exc_info=error)
        
        # Notify the user
        await ctx.send(f"❌ An error occurred: {str(error)}")
        
        # Notify bot owner
        owner = self.get_user(self.owner_id)
        if owner:
            await owner.send(f"Error in command `{ctx.command}`: {error}")

    def run(self, *args, **kwargs):
        """Run the bot with the token from environment variables."""
        token = os.getenv(f"{self.bot_type.upper()}_BOT_TOKEN")
        if not token:
            self.logger.error(f"{self.bot_type.upper()}_BOT_TOKEN not found in environment variables")
            return
            
        super().run(token, *args, **kwargs)
