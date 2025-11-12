# Phantom Scraper - Free Web Scraping Tool

A completely free, open-source alternative to PhantomBuster built with Python, Flask, and Selenium. This tool allows you to scrape data from LinkedIn, Google Maps, and any website without any monthly fees or usage limits.

## 🚀 Features

- **LinkedIn Profile Scraping**: Extract profiles from LinkedIn search results
- **Google Maps Business Scraping**: Scrape business listings from Google Maps
- **Custom Website Scraping**: Scrape any website using CSS selectors
- **Web Dashboard**: Easy-to-use interface for managing tasks
- **Data Export**: Export results to CSV, Excel, or JSON
- **Task Scheduling**: Schedule recurring scraping tasks
- **Anti-Detection**: Built-in measures to avoid detection
- **Free Forever**: No monthly fees, no usage limits

## 📋 Prerequisites

- Python 3.8 or higher
- Chrome browser installed
- Redis (optional, for advanced scheduling)

## 🛠️ Installation

1. **Clone or download the project**:
   ```bash
   cd /Users/mylesjadwin/Trading\ Projects/phantom_scraper
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Chrome WebDriver** (if not already installed):
   ```bash
   # On macOS with Homebrew
   brew install chromedriver
   
   # Or let the script handle it automatically
   ```

## 🚀 Quick Start

1. **Start the application**:
   ```bash
   python app.py
   ```

2. **Open your browser** and go to:
   ```
   http://localhost:5000
   ```

3. **Create your first scraping task**:
   - Click "Create New Task"
   - Choose your scraping type
   - Fill in the required fields
   - Click "Create Task"

## 📖 Usage Guide

### LinkedIn Profile Scraping

1. Go to LinkedIn and search for profiles
2. Copy the search URL
3. Create a new task with type "LinkedIn Profiles"
4. Paste the URL and set max profiles
5. Run the task

**Example LinkedIn Search URL**:
```
https://www.linkedin.com/search/results/people/?keywords=software%20engineer&location=San%20Francisco
```

### Google Maps Business Scraping

1. Create a new task with type "Google Maps"
2. Enter your search query (e.g., "restaurants near me")
3. Set the maximum number of results
4. Run the task

### Custom Website Scraping

1. Create a new task with type "Website Data"
2. Enter the target URL
3. Define CSS selectors in JSON format:
   ```json
   {
     "title": "h1",
     "description": ".description",
     "price": ".price",
     "links": "a"
   }
   ```
4. Run the task

### Testing Your Scraper

Before running a full task, use the "Test Scraper" feature to verify your selectors work correctly.

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
# Redis Configuration (optional)
REDIS_URL=redis://localhost:6379/0

# Database Configuration
DATABASE_URL=sqlite:///phantom_scraper.db

# Browser Configuration
HEADLESS=True

# Rate Limiting
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=3600
```

### Advanced Configuration

Edit `config.py` to customize:
- Request delays
- Retry attempts
- Output directories
- Logging levels

## 📊 Data Export

All scraped data is automatically saved in multiple formats:
- **JSON**: Raw data format
- **CSV**: Spreadsheet format
- **Excel**: Excel workbook format

Files are saved in the `output/` directory with timestamps.

## 🔄 Task Scheduling

For advanced scheduling with Redis:

1. **Install Redis**:
   ```bash
   # On macOS
   brew install redis
   brew services start redis
   ```

2. **Start Celery worker**:
   ```bash
   celery -A core.scheduler worker --loglevel=info
   ```

3. **Start Celery beat** (for scheduled tasks):
   ```bash
   celery -A core.scheduler beat --loglevel=info
   ```

## 🛡️ Anti-Detection Features

- **Random delays** between requests
- **User agent rotation**
- **Undetected Chrome driver**
- **Human-like scrolling behavior**
- **Request rate limiting**

## 📁 Project Structure

```
phantom_scraper/
├── app.py                 # Flask web application
├── config.py             # Configuration settings
├── requirements.txt      # Python dependencies
├── core/
│   ├── scraper.py       # Main scraping engine
│   ├── scheduler.py     # Task scheduling system
│   └── data_manager.py  # Data storage and export
├── templates/
│   └── index.html       # Web dashboard
├── output/              # Scraped data files
└── phantom_scraper.db   # SQLite database
```

## 🚨 Important Notes

### Legal Compliance
- Always respect website terms of service
- Don't scrape personal data without permission
- Use reasonable delays between requests
- Consider robots.txt files

### Rate Limiting
- Default: 100 requests per hour
- Adjust in `config.py` if needed
- Some sites may have stricter limits

### Troubleshooting

**Chrome driver issues**:
```bash
# Update Chrome and reinstall driver
pip install --upgrade selenium
```

**Memory issues**:
- Reduce `max_profiles` or `max_results`
- Run tasks in smaller batches

**Detection issues**:
- Increase delays in `scraper.py`
- Use different user agents
- Consider using residential proxies

## 🔧 Customization

### Adding New Scraping Types

1. Add new method to `PhantomScraper` class
2. Update task creation logic in `app.py`
3. Add UI fields in `templates/index.html`

### Custom Data Processing

Modify `data_manager.py` to add:
- Data validation
- Custom export formats
- Data transformation

## 📈 Performance Tips

1. **Use headless mode** for faster execution
2. **Adjust delays** based on target site
3. **Run multiple workers** for parallel processing
4. **Monitor memory usage** for large datasets

## 🤝 Contributing

This is a free, open-source project. Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Share improvements

## 📄 License

This project is free to use for any purpose. No restrictions, no fees, no limits.

## 🆘 Support

If you encounter issues:
1. Check the logs in the console
2. Verify your selectors with the test feature
3. Ensure Chrome is properly installed
4. Check your internet connection

---

**Happy Scraping! 🎉**

*Built with ❤️ as a free alternative to expensive scraping services*
