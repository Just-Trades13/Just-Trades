import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Redis Configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    
    # Database Configuration
    DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///phantom_scraper.db')
    
    # Scraping Configuration
    DEFAULT_DELAY = 2  # seconds between requests
    MAX_RETRIES = 3
    REQUEST_TIMEOUT = 30
    
    # Browser Configuration
    HEADLESS = os.getenv('HEADLESS', 'True').lower() == 'true'
    USER_AGENT_ROTATION = True
    
    # Output Configuration
    OUTPUT_DIR = 'output'
    LOG_LEVEL = 'INFO'
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS = 100  # requests per hour
    RATE_LIMIT_WINDOW = 3600  # 1 hour in seconds
