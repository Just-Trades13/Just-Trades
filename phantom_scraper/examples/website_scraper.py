#!/usr/bin/env python3
"""
Website Data Scraper Example
Demonstrates how to use the PhantomScraper for custom website data extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper import PhantomScraper
import json

def scrape_website_data():
    """Example: Scrape data from a website"""
    
    # Initialize scraper
    scraper = PhantomScraper(headless=False)  # Set to True for headless mode
    
    try:
        # Target website
        url = "https://quotes.toscrape.com/"
        
        # CSS selectors for data extraction
        selectors = {
            "quotes": ".quote .text",
            "authors": ".quote .author",
            "tags": ".quote .tag"
        }
        
        print("🔍 Scraping website data...")
        print(f"📋 URL: {url}")
        print(f"🎯 Selectors: {selectors}")
        
        # Scrape data
        data = scraper.scrape_website_data(url, selectors)
        
        print(f"✅ Scraped data successfully")
        
        # Display results
        print(f"\n📊 Results:")
        for key, value in data.items():
            if isinstance(value, list):
                print(f"   {key}: {len(value)} items")
                for i, item in enumerate(value[:3], 1):  # Show first 3 items
                    print(f"      {i}. {item}")
                if len(value) > 3:
                    print(f"      ... and {len(value) - 3} more")
            else:
                print(f"   {key}: {value}")
        
        # Save to file
        with open('website_data.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"\n💾 Results saved to website_data.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        scraper.stop()

if __name__ == "__main__":
    scrape_website_data()
