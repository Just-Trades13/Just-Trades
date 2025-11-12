#!/usr/bin/env python3
"""
Google Maps Business Scraper Example
Demonstrates how to use the PhantomScraper for Google Maps business extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper import PhantomScraper
import json

def scrape_google_maps():
    """Example: Scrape Google Maps businesses"""
    
    # Initialize scraper
    scraper = PhantomScraper(headless=False)  # Set to True for headless mode
    
    try:
        # Search query
        search_query = "restaurants near me"
        
        print("🔍 Scraping Google Maps businesses...")
        print(f"📋 Search Query: {search_query}")
        
        # Scrape businesses
        businesses = scraper.scrape_google_maps(search_query, max_results=10)
        
        print(f"✅ Found {len(businesses)} businesses")
        
        # Display results
        for i, business in enumerate(businesses, 1):
            print(f"\n🏢 Business {i}:")
            print(f"   Name: {business['name']}")
            print(f"   Rating: {business['rating']}")
            print(f"   Address: {business['address']}")
        
        # Save to file
        with open('google_maps_businesses.json', 'w') as f:
            json.dump(businesses, f, indent=2)
        
        print(f"\n💾 Results saved to google_maps_businesses.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        scraper.stop()

if __name__ == "__main__":
    scrape_google_maps()
