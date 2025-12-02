#!/usr/bin/env python3
"""
Simple test to verify the scraper is working
"""

import requests
import json

def test_scraper():
    print("🧪 Testing the scraper...")
    
    # Test the health endpoint
    try:
        response = requests.get("http://localhost:5004/health")
        print(f"✅ Health check: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"❌ Health check failed: {e}")
        return
    
    # Test the search endpoint
    try:
        search_data = {
            "query": "javascript developers",
            "searchType": "github"
        }
        
        response = requests.post(
            "http://localhost:5004/search",
            headers={"Content-Type": "application/json"},
            json=search_data
        )
        
        print(f"✅ Search request: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Check GitHub results
            github_data = data.get("formatted_sources", {}).get("github", {})
            developers = github_data.get("developers", [])
            
            print(f"📊 Found {len(developers)} GitHub developers")
            
            if developers:
                print("👨‍💻 Sample developers:")
                for i, dev in enumerate(developers[:3]):
                    print(f"   {i+1}. {dev.get('username', 'N/A')} - {dev.get('followers', 0)} followers")
            
            # Check other sources
            sources = data.get("sources", {})
            print(f"🔍 Sources searched: {list(sources.keys())}")
            
            # Check for errors
            for source, data in sources.items():
                if "error" in data:
                    print(f"⚠️  {source}: {data['error']}")
                else:
                    print(f"✅ {source}: Working")
                    
        else:
            print(f"❌ Search failed: {response.text}")
            
    except Exception as e:
        print(f"❌ Search test failed: {e}")

if __name__ == "__main__":
    test_scraper()
