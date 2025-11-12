#!/usr/bin/env python3
"""
LinkedIn Profile Scraper Example
Demonstrates how to use the PhantomScraper for LinkedIn profile extraction
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.scraper import PhantomScraper
import json

def scrape_linkedin_profiles():
    """Example: Scrape LinkedIn profiles"""
    
    # Initialize scraper
    scraper = PhantomScraper(headless=False)  # Set to True for headless mode
    
    try:
        # LinkedIn search URL (you need to manually search and copy the URL)
        search_url = "https://www.linkedin.com/search/results/people/?keywords=software%20engineer&location=San%20Francisco"
        
        print("🔍 Scraping LinkedIn profiles...")
        print(f"📋 Search URL: {search_url}")
        
        # Scrape profiles
        profiles = scraper.scrape_linkedin_profiles(search_url, max_profiles=10)
        
        print(f"✅ Found {len(profiles)} profiles")
        
        # Display results
        for i, profile in enumerate(profiles, 1):
            print(f"\n👤 Profile {i}:")
            print(f"   Name: {profile['name']}")
            print(f"   Title: {profile['title']}")
            print(f"   Company: {profile['company']}")
            print(f"   URL: {profile['profile_url']}")
        
        # Save to file
        with open('linkedin_profiles.json', 'w') as f:
            json.dump(profiles, f, indent=2)
        
        print(f"\n💾 Results saved to linkedin_profiles.json")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    
    finally:
        scraper.stop()

if __name__ == "__main__":
    scrape_linkedin_profiles()
