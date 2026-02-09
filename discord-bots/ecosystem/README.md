# Discord Trading Ecosystem

A comprehensive Discord bot ecosystem for traders and investors, providing real-time market data, educational resources, and trading tools.

## Features

- **Market Data Bot**: Real-time stock prices, news, and financial data
- **Education Bot**: Trading lessons, glossary, and educational resources
- **Analysis Bot**: Economic calendar and market analysis

## Setup

### Prerequisites

- Python 3.8 or higher
- Discord bot tokens (create at [Discord Developer Portal](https://discord.com/developers/applications))
- API keys for news and financial data (optional)

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/discord-trading-ecosystem.git
   cd discord-trading-ecosystem
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables:
   ```bash
   cp .env.template .env
   ```
   Edit the `.env` file and fill in your Discord bot tokens and other settings.

### Running the Bots

1. Run all bots together:
   ```bash
   python run_bots.py
   ```

2. Or run bots individually:
   ```bash
   python -m src.bots.market_data_bot.bot
   python -m src.bots.education_bot.bot
   python -m src.bots.analysis_bot.bot
   ```

## Bot Commands

### Market Data Bot
- `!stock <symbol>` - Get stock data (e.g., `!stock AAPL`)
- `!news [query] [limit=5]` - Get financial news

### Education Bot
- `!term <term>` - Look up a trading term
- `!lesson [level=beginner] [number=1]` - Get a trading lesson
- `!strategy <name>` - Get details about a trading strategy

### Analysis Bot
- `!calendar [days=7] [country=US]` - Get economic calendar
- `!bias` - Get current market bias

## Project Structure

```
discord-trading-ecosystem/
├── .env.template         # Template for environment variables
├── requirements.txt      # Python dependencies
├── run_bots.py           # Script to run all bots
├── src/                  # Source code
│   ├── bots/             # Bot implementations
│   │   ├── market_data_bot/
│   │   ├── education_bot/
│   │   └── analysis_bot/
│   ├── config/          # Configuration files
│   ├── services/         # Business logic and API clients
│   └── utils/            # Utility functions
└── tests/                # Unit and integration tests
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
