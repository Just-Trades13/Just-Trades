#!/usr/bin/env python3
"""
Script to run all trading bot components.
"""
import os
import sys
import asyncio
import logging
from dotenv import load_dotenv

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('trading_bots.log')
    ]
)

logger = logging.getLogger('bot_runner')

def check_environment():
    """Check if all required environment variables are set."""
    required_vars = [
        'MARKET_DATA_BOT_TOKEN',
        'EDUCATION_BOT_TOKEN',
        'ANALYSIS_BOT_TOKEN',
        'GUILD_ID'
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logger.info("Please copy .env.template to .env and fill in the required values")
        return False
    return True

async def run_bots():
    """Run all bot components."""
    from src.bots.market_data_bot import MarketDataBot
    from src.bots.education_bot import EducationBot
    from src.bots.analysis_bot import AnalysisBot
    
    # Create bot instances
    market_data_bot = MarketDataBot()
    education_bot = EducationBot()
    analysis_bot = AnalysisBot()
    
    # Start all bots
    tasks = [
        asyncio.create_task(market_data_bot.start(os.getenv('MARKET_DATA_BOT_TOKEN'))),
        asyncio.create_task(education_bot.start(os.getenv('EDUCATION_BOT_TOKEN'))),
        asyncio.create_task(analysis_bot.start(os.getenv('ANALYSIS_BOT_TOKEN')))
    ]
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        logger.info("Shutting down bots...")
        await market_data_bot.close()
        await education_bot.close()
        await analysis_bot.close()
    except Exception as e:
        logger.error(f"Error running bots: {e}", exc_info=True)
    finally:
        logger.info("All bots have been shut down")

def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Check environment
    if not check_environment():
        sys.exit(1)
    
    # Run bots
    try:
        asyncio.run(run_bots())
    except KeyboardInterrupt:
        logger.info("Bot runner stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
