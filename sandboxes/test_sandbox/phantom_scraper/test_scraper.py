#!/usr/bin/env python3
"""
Test the scraper functionality
"""

import sys
import os
sys.path.append('.')

from simple_scraper import SimpleScraper

def test_scraper():
    print("🧪 Testing Simple Scraper...")
    
    scraper = SimpleScraper()
    
    # Test 1: Start browser
    print("1. Testing browser startup...")
    if scraper.start_browser(headless=True):
        print("✅ Browser started successfully")
    else:
        print("❌ Browser failed to start")
        return
    
    # Test 2: Scrape a simple website
    print("2. Testing website scraping...")
    test_url = "https://quotes.toscrape.com/"
    selectors = {
        "quotes": ".quote .text",
        "authors": ".quote .author"
    }
    
    result = scraper.scrape_website(test_url, selectors, max_results=3)
    
    if "error" in result:
        print(f"❌ Scraping failed: {result['error']}")
    else:
        print("✅ Scraping successful!")
        print(f"Results: {result['results']}")
    
    # Test 3: Clean up
    print("3. Cleaning up...")
    scraper.stop_browser()
    print("✅ Test complete!")

if __name__ == "__main__":
    test_scraper()
