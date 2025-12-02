#!/usr/bin/env python3
"""
Easy Scraper - Multiple API Sources
Uses Apollo, Clearbit, Hunter, and web scraping
No complex LinkedIn setup required
"""

import requests
import json
import time
import csv
import io
from flask import Flask, render_template_string, request, jsonify, send_file
from flask_cors import CORS
import pandas as pd
from datetime import datetime
import base64

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# API Keys (you'll need to get these - much easier than LinkedIn)
APOLLO_API_KEY = "jVyq9ZzhNeiGYLoVXNkxhg"
CLEARBIT_API_KEY = "your_clearbit_key_here"
HUNTER_API_KEY = "your_hunter_key_here"
SCRAPINGBEE_API_KEY = "your_scrapingbee_key_here"

class EasyScraper:
    def __init__(self):
        self.results = []
        self.search_history = []
    
    def format_apollo_results(self, data):
        """Format Apollo.io results for better display"""
        if "error" in data:
            return data
        
        formatted_results = {
            "total_count": data.get("pagination", {}).get("total_entries", 0),
            "contacts": []
        }
        
        for person in data.get("people", []):
            contact = {
                "name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
                "title": person.get("title", "N/A"),
                "company": person.get("organization", {}).get("name", "N/A"),
                "location": person.get("city", "N/A") + ", " + person.get("state", "N/A"),
                "linkedin_url": person.get("linkedin_url", "N/A"),
                "email": person.get("email", "N/A"),
                "phone": person.get("phone_numbers", [{}])[0].get("raw_number", "N/A") if person.get("phone_numbers") else "N/A",
                "company_size": person.get("organization", {}).get("estimated_num_employees", "N/A"),
                "industry": person.get("organization", {}).get("industry", "N/A")
            }
            formatted_results["contacts"].append(contact)
        
        return formatted_results
    
    def format_github_results(self, data):
        """Format GitHub results for better display"""
        if "error" in data:
            return data
        
        formatted_results = {
            "total_count": data.get("total_count", 0),
            "developers": []
        }
        
        for user in data.get("users", []):
            developer = {
                "username": user.get("login", "N/A"),
                "name": user.get("name", "N/A"),
                "company": user.get("company", "N/A"),
                "location": user.get("location", "N/A"),
                "followers": user.get("followers", 0),
                "public_repos": user.get("public_repos", 0),
                "profile_url": user.get("html_url", "N/A"),
                "avatar_url": user.get("avatar_url", "N/A"),
                "bio": user.get("bio", "N/A")
            }
            formatted_results["developers"].append(developer)
        
        return formatted_results
    
    def export_to_csv(self, data, filename="scraper_results.csv"):
        """Export search results to CSV"""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        writer.writerow(["Source", "Name", "Title", "Company", "Location", "Email", "Phone", "Profile URL", "Additional Info"])
        
        # Write Apollo results
        if "apollo" in data.get("sources", {}):
            apollo_data = data["sources"]["apollo"]
            if "contacts" in apollo_data:
                for contact in apollo_data["contacts"]:
                    writer.writerow([
                        "Apollo.io",
                        contact.get("name", ""),
                        contact.get("title", ""),
                        contact.get("company", ""),
                        contact.get("location", ""),
                        contact.get("email", ""),
                        contact.get("phone", ""),
                        contact.get("linkedin_url", ""),
                        f"Industry: {contact.get('industry', '')}, Company Size: {contact.get('company_size', '')}"
                    ])
        
        # Write GitHub results
        if "github" in data.get("sources", {}):
            github_data = data["sources"]["github"]
            if "developers" in github_data:
                for dev in github_data["developers"]:
                    writer.writerow([
                        "GitHub",
                        dev.get("name", ""),
                        "Developer",
                        dev.get("company", ""),
                        dev.get("location", ""),
                        "N/A",
                        "N/A",
                        dev.get("profile_url", ""),
                        f"Followers: {dev.get('followers', 0)}, Repos: {dev.get('public_repos', 0)}"
                    ])
        
        return output.getvalue()
    
    def search_apollo(self, query, limit=10):
        """Search Apollo.io for professional contacts"""
        try:
            if APOLLO_API_KEY == "your_apollo_key_here":
                return {"error": "Apollo.io API key not configured. Please get your API key from apollo.io and update the code."}
            
            url = "https://api.apollo.io/v1/mixed_people/search"
            headers = {
                "Cache-Control": "no-cache",
                "Content-Type": "application/json",
                "X-Api-Key": APOLLO_API_KEY
            }
            
            data = {
                "q_keywords": query,
                "page": 1,
                "per_page": limit,
                "person_titles": ["CEO", "CTO", "Founder", "Director", "Manager"],
                "person_locations": ["United States", "Canada", "United Kingdom"]
            }
            
            response = requests.post(url, headers=headers, json=data)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                return {"error": "Apollo.io requires a paid plan for People Search API. Your free plan doesn't include this feature. Upgrade at https://app.apollo.io/"}
            else:
                return {"error": f"Apollo API error: {response.status_code} - {response.text[:200]}"}
        except Exception as e:
            return {"error": f"Apollo search failed: {str(e)}"}
    
    def enrich_clearbit(self, email):
        """Enrich contact data using Clearbit"""
        try:
            url = f"https://person.clearbit.com/v2/people/find?email={email}"
            headers = {"Authorization": f"Bearer {CLEARBIT_API_KEY}"}
            
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Clearbit API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Clearbit enrichment failed: {str(e)}"}
    
    def find_email_hunter(self, domain, first_name, last_name):
        """Find email using Hunter.io"""
        try:
            url = f"https://api.hunter.io/v2/email-finder"
            params = {
                "domain": domain,
                "first_name": first_name,
                "last_name": last_name,
                "api_key": HUNTER_API_KEY
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"Hunter API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Hunter search failed: {str(e)}"}
    
    def scrape_website(self, url):
        """Scrape website using ScrapingBee"""
        try:
            api_url = "https://app.scrapingbee.com/api/v1/"
            params = {
                "api_key": SCRAPINGBEE_API_KEY,
                "url": url,
                "render_js": "true",
                "premium_proxy": "true"
            }
            
            response = requests.get(api_url, params=params)
            if response.status_code == 200:
                return {"content": response.text, "status": "success"}
            else:
                return {"error": f"ScrapingBee error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Website scraping failed: {str(e)}"}
    
    def search_google_maps(self, query, location="United States"):
        """Search Google Maps for businesses"""
        try:
            # This is a simplified version - you'd need Google Places API for full functionality
            search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
            return {"search_url": search_url, "note": "Use Google Places API for full data"}
        except Exception as e:
            return {"error": f"Google Maps search failed: {str(e)}"}
    
    def search_github_users(self, query, limit=10):
        """Search GitHub for developers and professionals"""
        try:
            url = "https://api.github.com/search/users"
            params = {
                "q": f"{query} type:user",
                "per_page": limit,
                "sort": "followers"
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                users = data.get("items", [])
                
                # Get detailed profile information for each user
                detailed_users = []
                for user in users:
                    try:
                        # Get full user profile
                        profile_url = user.get("url")
                        if profile_url:
                            profile_response = requests.get(profile_url)
                            if profile_response.status_code == 200:
                                profile_data = profile_response.json()
                                detailed_users.append({
                                    "login": profile_data.get("login", "N/A"),
                                    "name": profile_data.get("name", "N/A"),
                                    "company": profile_data.get("company", "N/A"),
                                    "location": profile_data.get("location", "N/A"),
                                    "followers": profile_data.get("followers", 0),
                                    "public_repos": profile_data.get("public_repos", 0),
                                    "html_url": profile_data.get("html_url", "N/A"),
                                    "avatar_url": profile_data.get("avatar_url", "N/A"),
                                    "bio": profile_data.get("bio", "N/A")
                                })
                            else:
                                # Fallback to basic data if profile fetch fails
                                detailed_users.append({
                                    "login": user.get("login", "N/A"),
                                    "name": "N/A",
                                    "company": "N/A",
                                    "location": "N/A",
                                    "followers": 0,
                                    "public_repos": 0,
                                    "html_url": user.get("html_url", "N/A"),
                                    "avatar_url": user.get("avatar_url", "N/A"),
                                    "bio": "N/A"
                                })
                    except Exception as e:
                        print(f"Error fetching profile for {user.get('login', 'unknown')}: {e}")
                        # Add basic user data if profile fetch fails
                        detailed_users.append({
                            "login": user.get("login", "N/A"),
                            "name": "N/A",
                            "company": "N/A",
                            "location": "N/A",
                            "followers": 0,
                            "public_repos": 0,
                            "html_url": user.get("html_url", "N/A"),
                            "avatar_url": user.get("avatar_url", "N/A"),
                            "bio": "N/A"
                        })
                
                return {
                    "total_count": data.get("total_count", 0),
                    "users": detailed_users,
                    "note": "GitHub API - Free tier available"
                }
            else:
                return {"error": f"GitHub API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"GitHub search failed: {str(e)}"}
    
    def search_company_websites(self, query):
        """Search for company websites and basic info"""
        try:
            # This is a mock search - in reality you'd use a company database API
            companies = [
                {"name": f"{query} Inc.", "website": f"https://{query.lower().replace(' ', '')}.com", "industry": "Technology"},
                {"name": f"{query} Corp.", "website": f"https://{query.lower().replace(' ', '')}.io", "industry": "Software"},
                {"name": f"{query} LLC", "website": f"https://{query.lower().replace(' ', '')}.net", "industry": "Services"}
            ]
            return {
                "companies": companies,
                "note": "Mock data - Use real company database API for actual data"
            }
        except Exception as e:
            return {"error": f"Company search failed: {str(e)}"}
    
    def search_reddit_users(self, query, limit=10):
        """Search Reddit for users and posts related to the query"""
        try:
            url = f"https://www.reddit.com/search.json"
            params = {
                "q": query,
                "limit": limit,
                "sort": "relevance"
            }
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                users = []
                for post in data.get("data", {}).get("children", []):
                    post_data = post.get("data", {})
                    users.append({
                        "username": post_data.get("author", "N/A"),
                        "title": post_data.get("title", "N/A"),
                        "subreddit": post_data.get("subreddit", "N/A"),
                        "score": post_data.get("score", 0),
                        "url": f"https://reddit.com{post_data.get('permalink', '')}",
                        "created": post_data.get("created_utc", 0)
                    })
                
                return {
                    "total_count": len(users),
                    "users": users,
                    "note": "Reddit API - Free tier available"
                }
            else:
                return {"error": f"Reddit API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Reddit search failed: {str(e)}"}
    
    def search_hackernews(self, query, limit=10):
        """Search Hacker News for relevant posts and users"""
        try:
            url = "https://hn.algolia.com/api/v1/search"
            params = {
                "query": query,
                "hitsPerPage": limit,
                "tags": "story"
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                posts = []
                for hit in data.get("hits", []):
                    posts.append({
                        "title": hit.get("title", "N/A"),
                        "author": hit.get("author", "N/A"),
                        "url": hit.get("url", "N/A"),
                        "points": hit.get("points", 0),
                        "comments": hit.get("num_comments", 0),
                        "created_at": hit.get("created_at", "N/A")
                    })
                
                return {
                    "total_count": len(posts),
                    "posts": posts,
                    "note": "Hacker News API - Free"
                }
            else:
                return {"error": f"Hacker News API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Hacker News search failed: {str(e)}"}
    
    def search_stackoverflow(self, query, limit=10):
        """Search Stack Overflow for developers and questions"""
        try:
            url = "https://api.stackexchange.com/2.3/search/advanced"
            params = {
                "order": "desc",
                "sort": "relevance",
                "q": query,
                "site": "stackoverflow",
                "pagesize": limit
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                questions = []
                for item in data.get("items", []):
                    questions.append({
                        "title": item.get("title", "N/A"),
                        "author": item.get("owner", {}).get("display_name", "N/A"),
                        "author_id": item.get("owner", {}).get("user_id", "N/A"),
                        "score": item.get("score", 0),
                        "answers": item.get("answer_count", 0),
                        "views": item.get("view_count", 0),
                        "tags": item.get("tags", []),
                        "url": item.get("link", "N/A"),
                        "created": item.get("creation_date", 0)
                    })
                
                return {
                    "total_count": len(questions),
                    "questions": questions,
                    "note": "Stack Overflow API - Free"
                }
            else:
                return {"error": f"Stack Overflow API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Stack Overflow search failed: {str(e)}"}
    
    def search_producthunt(self, query, limit=10):
        """Search Product Hunt for products and makers"""
        try:
            # Using Product Hunt's public API (unofficial)
            url = "https://api.producthunt.com/v1/posts"
            headers = {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "Bearer YOUR_TOKEN"  # This would need a token
            }
            
            # For now, return mock data since Product Hunt requires authentication
            products = [
                {
                    "name": f"{query} App",
                    "tagline": f"The best {query} solution",
                    "maker": f"{query} Team",
                    "votes": 150,
                    "comments": 25,
                    "url": f"https://producthunt.com/posts/{query.lower().replace(' ', '-')}"
                },
                {
                    "name": f"{query} Pro",
                    "tagline": f"Professional {query} tools",
                    "maker": f"{query} Inc",
                    "votes": 89,
                    "comments": 12,
                    "url": f"https://producthunt.com/posts/{query.lower().replace(' ', '-')}-pro"
                }
            ]
            
            return {
                "total_count": len(products),
                "products": products,
                "note": "Product Hunt - Mock data (API requires authentication)"
            }
        except Exception as e:
            return {"error": f"Product Hunt search failed: {str(e)}"}
    
    def search_medium(self, query, limit=10):
        """Search Medium for articles and authors"""
        try:
            # Using Medium's RSS feed (free)
            import feedparser
            url = f"https://medium.com/feed/tag/{query.replace(' ', '-')}"
            
            feed = feedparser.parse(url)
            articles = []
            
            for entry in feed.entries[:limit]:
                articles.append({
                    "title": entry.get("title", "N/A"),
                    "author": entry.get("author", "N/A"),
                    "summary": entry.get("summary", "N/A")[:200] + "...",
                    "url": entry.get("link", "N/A"),
                    "published": entry.get("published", "N/A")
                })
            
            return {
                "total_count": len(articles),
                "articles": articles,
                "note": "Medium RSS - Free"
            }
        except Exception as e:
            return {"error": f"Medium search failed: {str(e)}"}
    
    def search_google_scholar(self, query, limit=10):
        """Search Google Scholar for academic papers and authors"""
        try:
            # This is a simplified version - in reality you'd need to scrape or use an API
            papers = [
                {
                    "title": f"Research on {query}: A Comprehensive Study",
                    "authors": f"Dr. {query} Researcher, Prof. Academic",
                    "journal": f"Journal of {query} Studies",
                    "year": "2024",
                    "citations": 45,
                    "url": f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"
                },
                {
                    "title": f"Advanced {query} Techniques and Applications",
                    "authors": f"Dr. Tech Expert, Dr. Innovation Lead",
                    "journal": f"International {query} Review",
                    "year": "2023",
                    "citations": 32,
                    "url": f"https://scholar.google.com/scholar?q={query.replace(' ', '+')}"
                }
            ]
            
            return {
                "total_count": len(papers),
                "papers": papers,
                "note": "Google Scholar - Mock data (would need scraping for real data)"
            }
        except Exception as e:
            return {"error": f"Google Scholar search failed: {str(e)}"}
    
    def run_comprehensive_search(self, query, search_type="all"):
        """Run a comprehensive search across multiple sources"""
        results = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "sources": {},
            "formatted_sources": {}
        }
        
        if search_type in ["all", "apollo"]:
            print(f"🔍 Searching Apollo.io for: {query}")
            apollo_data = self.search_apollo(query)
            results["sources"]["apollo"] = apollo_data
            results["formatted_sources"]["apollo"] = self.format_apollo_results(apollo_data)
        
        if search_type in ["all", "github"]:
            print(f"👨‍💻 Searching GitHub for: {query}")
            github_data = self.search_github_users(query)
            results["sources"]["github"] = github_data
            results["formatted_sources"]["github"] = self.format_github_results(github_data)
        
        if search_type in ["all", "reddit"]:
            print(f"🔴 Searching Reddit for: {query}")
            reddit_data = self.search_reddit_users(query)
            results["sources"]["reddit"] = reddit_data
        
        if search_type in ["all", "hackernews"]:
            print(f"📰 Searching Hacker News for: {query}")
            hn_data = self.search_hackernews(query)
            results["sources"]["hackernews"] = hn_data
        
        if search_type in ["all", "stackoverflow"]:
            print(f"💻 Searching Stack Overflow for: {query}")
            so_data = self.search_stackoverflow(query)
            results["sources"]["stackoverflow"] = so_data
        
        if search_type in ["all", "medium"]:
            print(f"📝 Searching Medium for: {query}")
            medium_data = self.search_medium(query)
            results["sources"]["medium"] = medium_data
        
        if search_type in ["all", "producthunt"]:
            print(f"🚀 Searching Product Hunt for: {query}")
            ph_data = self.search_producthunt(query)
            results["sources"]["producthunt"] = ph_data
        
        if search_type in ["all", "scholar"]:
            print(f"🎓 Searching Google Scholar for: {query}")
            scholar_data = self.search_google_scholar(query)
            results["sources"]["scholar"] = scholar_data
        
        if search_type in ["all", "companies"]:
            print(f"🏢 Searching companies for: {query}")
            results["sources"]["companies"] = self.search_company_websites(query)
        
        if search_type in ["all", "maps"]:
            print(f"🗺️ Searching Google Maps for: {query}")
            results["sources"]["google_maps"] = self.search_google_maps(query)
        
        if search_type in ["all", "website"]:
            print(f"🌐 Scraping website: {query}")
            results["sources"]["website"] = self.scrape_website(query)
        
        # Add to search history
        self.search_history.append({
            "query": query,
            "search_type": search_type,
            "timestamp": datetime.now().isoformat(),
            "results_count": sum(len(data.get("contacts", [])) + len(data.get("developers", [])) 
                               for data in results["formatted_sources"].values() 
                               if isinstance(data, dict))
        })
        
        return results

# Initialize scraper
scraper = EasyScraper()

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Professional Scraper - Apollo.io & More</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        .container { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header { 
            text-align: center; 
            margin-bottom: 40px; 
            background: rgba(255,255,255,0.95);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }
        .header h1 { 
            color: #2c3e50; 
            font-size: 3em; 
            margin: 0; 
            font-weight: 700;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .header p { color: #7f8c8d; font-size: 1.3em; margin: 15px 0; }
        .stats-bar {
            display: flex;
            justify-content: space-around;
            background: rgba(255,255,255,0.9);
            padding: 20px;
            border-radius: 15px;
            margin-bottom: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
        }
        .stat-item { text-align: center; }
        .stat-number { font-size: 2em; font-weight: bold; color: #667eea; }
        .stat-label { color: #7f8c8d; font-size: 0.9em; }
        .search-box { 
            background: rgba(255,255,255,0.95); 
            padding: 40px; 
            border-radius: 20px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); 
            margin-bottom: 30px; 
        }
        .search-box h2 { margin-bottom: 30px; color: #2c3e50; font-size: 1.8em; }
        .form-row { display: flex; gap: 20px; margin-bottom: 25px; }
        .form-group { flex: 1; }
        .form-group label { 
            display: block; 
            margin-bottom: 10px; 
            font-weight: 600; 
            color: #2c3e50; 
            font-size: 1.1em;
        }
        .form-group input, .form-group select { 
            width: 100%; 
            padding: 15px; 
            border: 2px solid #e1e8ed; 
            border-radius: 12px; 
            font-size: 16px; 
            transition: all 0.3s ease;
            background: #f8f9fa;
        }
        .form-group input:focus, .form-group select:focus { 
            outline: none; 
            border-color: #667eea; 
            background: white;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        .btn { 
            background: linear-gradient(45deg, #667eea, #764ba2); 
            color: white; 
            padding: 15px 30px; 
            border: none; 
            border-radius: 12px; 
            font-size: 16px; 
            font-weight: 600;
            cursor: pointer; 
            transition: all 0.3s ease;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }
        .btn:hover { 
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
        }
        .btn:disabled { 
            background: #bdc3c7; 
            cursor: not-allowed; 
            transform: none;
            box-shadow: none;
        }
        .results { 
            background: rgba(255,255,255,0.95); 
            padding: 40px; 
            border-radius: 20px; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.1); 
            margin-bottom: 30px;
        }
        .results h2 { margin-bottom: 30px; color: #2c3e50; font-size: 1.8em; }
        .source { 
            margin-bottom: 40px; 
            padding: 30px; 
            border: 2px solid #e1e8ed; 
            border-radius: 15px; 
            background: #f8f9fa;
            transition: all 0.3s ease;
        }
        .source:hover { border-color: #667eea; box-shadow: 0 5px 15px rgba(102, 126, 234, 0.1); }
        .source h3 { 
            margin-bottom: 20px; 
            color: #667eea; 
            font-size: 1.4em;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .contact-card, .developer-card {
            background: white;
            padding: 20px;
            margin: 15px 0;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            border-left: 4px solid #667eea;
        }
        .contact-name, .developer-name { 
            font-size: 1.2em; 
            font-weight: bold; 
            color: #2c3e50; 
            margin-bottom: 8px;
        }
        .contact-title, .developer-company { 
            color: #7f8c8d; 
            margin-bottom: 5px;
        }
        .contact-company, .developer-location { 
            color: #95a5a6; 
            font-size: 0.9em;
        }
        .contact-email, .contact-phone {
            color: #667eea;
            font-size: 0.9em;
            margin-top: 8px;
        }
        .loading { 
            text-align: center; 
            padding: 60px; 
            color: #7f8c8d; 
            font-size: 1.2em;
        }
        .error { 
            color: #e74c3c; 
            background: #fdf2f2; 
            padding: 20px; 
            border-radius: 12px; 
            margin: 20px 0; 
            border-left: 4px solid #e74c3c;
        }
        .success { 
            color: #27ae60; 
            background: #f0f9f4; 
            padding: 20px; 
            border-radius: 12px; 
            margin: 20px 0; 
            border-left: 4px solid #27ae60;
        }
        .api-status { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); 
            gap: 25px; 
            margin-bottom: 40px; 
        }
        .api-card { 
            background: rgba(255,255,255,0.9); 
            padding: 25px; 
            border-radius: 15px; 
            box-shadow: 0 10px 30px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
        }
        .api-card:hover { transform: translateY(-5px); box-shadow: 0 15px 40px rgba(0,0,0,0.15); }
        .api-card h3 { margin-bottom: 15px; color: #2c3e50; font-size: 1.3em; }
        .api-card p { color: #7f8c8d; margin-bottom: 15px; }
        .status { 
            padding: 8px 16px; 
            border-radius: 20px; 
            font-size: 0.9em; 
            font-weight: 600; 
            display: inline-block;
        }
        .status.ready { background: #d5f4e6; color: #27ae60; }
        .status.setup { background: #fff3cd; color: #f39c12; }
        .export-btn {
            background: linear-gradient(45deg, #27ae60, #2ecc71);
            margin-left: 10px;
        }
        .export-btn:hover {
            box-shadow: 0 6px 20px rgba(39, 174, 96, 0.4);
        }
        .tabs {
            display: flex;
            margin-bottom: 20px;
            background: #f8f9fa;
            border-radius: 12px;
            padding: 5px;
        }
        .tab {
            flex: 1;
            padding: 12px 20px;
            text-align: center;
            cursor: pointer;
            border-radius: 8px;
            transition: all 0.3s ease;
            font-weight: 600;
        }
        .tab.active {
            background: white;
            color: #667eea;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
        @media (max-width: 768px) {
            .form-row { flex-direction: column; }
            .header h1 { font-size: 2em; }
            .stats-bar { flex-direction: column; gap: 15px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Professional Scraper</h1>
            <p>Apollo.io, GitHub, and more - Find contacts, developers, and companies</p>
        </div>

        <div class="stats-bar" id="statsBar">
            <div class="stat-item">
                <div class="stat-number" id="totalSearches">0</div>
                <div class="stat-label">Total Searches</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="totalContacts">0</div>
                <div class="stat-label">Contacts Found</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="totalDevelopers">0</div>
                <div class="stat-label">Developers Found</div>
            </div>
            <div class="stat-item">
                <div class="stat-number" id="apolloStatus">✅</div>
                <div class="stat-label">Apollo.io Status</div>
            </div>
        </div>

        <div class="api-status">
            <div class="api-card">
                <h3>🔍 Apollo.io</h3>
                <p>Professional contacts, companies, and detailed business data</p>
                <span class="status ready">✅ Configured</span>
            </div>
            <div class="api-card">
                <h3>👨‍💻 GitHub</h3>
                <p>Find developers, their projects, and technical profiles</p>
                <span class="status ready">✅ Free</span>
            </div>
            <div class="api-card">
                <h3>🏢 Companies</h3>
                <p>Company information and business intelligence</p>
                <span class="status ready">✅ Free</span>
            </div>
            <div class="api-card">
                <h3>🗺️ Google Maps</h3>
                <p>Business locations and local company data</p>
                <span class="status ready">✅ Free</span>
            </div>
        </div>

        <div class="search-box">
            <h2>🔍 Advanced Search</h2>
            <form id="searchForm">
                <div class="form-row">
                    <div class="form-group">
                        <label for="query">Search Query:</label>
                        <input type="text" id="query" name="query" placeholder="e.g., 'software companies in San Francisco', 'React developers', 'CEO at tech startups'" required>
                    </div>
                    <div class="form-group">
                        <label for="searchType">Search Type:</label>
                        <select id="searchType" name="searchType">
                            <option value="all">All Free Sources</option>
                            <option value="github">GitHub Developers (Free)</option>
                            <option value="reddit">Reddit Users (Free)</option>
                            <option value="hackernews">Hacker News (Free)</option>
                            <option value="stackoverflow">Stack Overflow (Free)</option>
                            <option value="medium">Medium Articles (Free)</option>
                            <option value="producthunt">Product Hunt (Free)</option>
                            <option value="scholar">Google Scholar (Free)</option>
                            <option value="companies">Companies (Free)</option>
                            <option value="maps">Google Maps (Free)</option>
                        </select>
                    </div>
                </div>
                <button type="submit" class="btn" id="searchBtn">🔍 Search Now</button>
                <button type="button" class="btn export-btn" id="exportBtn" style="display: none;">📊 Export Results</button>
            </form>
        </div>

        <div class="results" id="results" style="display: none;">
            <div class="tabs">
                <div class="tab active" data-tab="contacts">👥 Contacts</div>
                <div class="tab" data-tab="developers">👨‍💻 Developers</div>
                <div class="tab" data-tab="raw">📋 Raw Data</div>
            </div>
            
            <div class="tab-content active" id="contacts-tab">
                <h2>📊 Professional Contacts</h2>
                <div id="contactsContent"></div>
            </div>
            
            <div class="tab-content" id="developers-tab">
                <h2>👨‍💻 Developers</h2>
                <div id="developersContent"></div>
            </div>
            
            <div class="tab-content" id="raw-tab">
                <h2>📋 Raw API Data</h2>
                <div id="rawContent"></div>
            </div>
        </div>
    </div>

    <script>
        let currentResults = null;
        
        // Load stats on page load
        async function loadStats() {
            try {
                const response = await fetch('/stats');
                const stats = await response.json();
                document.getElementById('totalSearches').textContent = stats.total_searches || 0;
                document.getElementById('totalContacts').textContent = stats.total_contacts_found || 0;
                document.getElementById('totalDevelopers').textContent = stats.total_developers_found || 0;
                document.getElementById('apolloStatus').textContent = stats.apollo_api_configured ? '✅' : '❌';
            } catch (error) {
                console.error('Error loading stats:', error);
            }
        }
        
        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab + '-tab').classList.add('active');
            });
        });
        
        // Search form
        document.getElementById('searchForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const query = document.getElementById('query').value;
            const searchType = document.getElementById('searchType').value;
            const searchBtn = document.getElementById('searchBtn');
            const results = document.getElementById('results');
            const exportBtn = document.getElementById('exportBtn');
            
            console.log('Starting search:', { query, searchType });
            
            searchBtn.disabled = true;
            searchBtn.textContent = '🔍 Searching...';
            results.style.display = 'block';
            exportBtn.style.display = 'none';
            
            // Show loading in all tabs
            document.getElementById('contactsContent').innerHTML = '<div class="loading">🔍 Searching for contacts...</div>';
            document.getElementById('developersContent').innerHTML = '<div class="loading">🔍 Searching for developers...</div>';
            document.getElementById('rawContent').innerHTML = '<div class="loading">🔍 Fetching raw data...</div>';
            
            try {
                console.log('Making API request...');
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, searchType })
                });
                
                console.log('Response status:', response.status);
                const data = await response.json();
                console.log('Response data:', data);
                currentResults = data;
                
                if (data.error) {
                    console.error('API error:', data.error);
                    document.getElementById('contactsContent').innerHTML = `<div class="error">❌ Error: ${data.error}</div>`;
                } else {
                    console.log('Search successful, displaying results...');
                    displayResults(data);
                    exportBtn.style.display = 'inline-block';
                    loadStats(); // Refresh stats
                }
            } catch (error) {
                console.error('Fetch error:', error);
                document.getElementById('contactsContent').innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = '🔍 Search Now';
            }
        });
        
        function displayResults(data) {
            console.log('Displaying results:', data); // Debug log
            
            // Add success message
            let contactsHtml = '<div class="success">✅ Search completed successfully! Check the tabs below for results.</div>';
            
            // Display contacts
            if (data.formatted_sources && data.formatted_sources.apollo && data.formatted_sources.apollo.contacts) {
                const contacts = data.formatted_sources.apollo.contacts;
                contacts.forEach(contact => {
                    contactsHtml += `
                        <div class="contact-card">
                            <div class="contact-name">${contact.name}</div>
                            <div class="contact-title">${contact.title}</div>
                            <div class="contact-company">${contact.company}</div>
                            <div class="contact-company">${contact.location}</div>
                            <div class="contact-email">📧 ${contact.email}</div>
                            <div class="contact-phone">📞 ${contact.phone}</div>
                        </div>
                    `;
                });
            } else {
                contactsHtml += '<div class="loading">No professional contacts found. Try Apollo.io with a paid plan for contact data.</div>';
            }
            
            document.getElementById('contactsContent').innerHTML = contactsHtml;
            
            // Display developers
            let developersHtml = '';
            if (data.formatted_sources && data.formatted_sources.github && data.formatted_sources.github.developers) {
                const developers = data.formatted_sources.github.developers;
                developers.forEach(dev => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">${dev.name || dev.username}</div>
                            <div class="developer-company">${dev.company || 'Independent'}</div>
                            <div class="developer-location">📍 ${dev.location || 'Unknown'}</div>
                            <div class="developer-location">👥 ${dev.followers} followers • 📦 ${dev.public_repos} repos</div>
                        </div>
                    `;
                });
            }
            
            // Display Reddit users
            if (data.sources && data.sources.reddit && data.sources.reddit.users) {
                const redditUsers = data.sources.reddit.users;
                redditUsers.forEach(user => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">🔴 u/${user.username}</div>
                            <div class="developer-company">${user.title}</div>
                            <div class="developer-location">r/${user.subreddit} • ⬆️ ${user.score} points</div>
                            <div class="developer-location">🔗 <a href="${user.url}" target="_blank">View Post</a></div>
                        </div>
                    `;
                });
            }
            
            // Display Hacker News posts
            if (data.sources && data.sources.hackernews && data.sources.hackernews.posts) {
                const hnPosts = data.sources.hackernews.posts;
                hnPosts.forEach(post => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">📰 ${post.title}</div>
                            <div class="developer-company">by ${post.author}</div>
                            <div class="developer-location">⬆️ ${post.points} points • 💬 ${post.comments} comments</div>
                            <div class="developer-location">🔗 <a href="${post.url}" target="_blank">Read More</a></div>
                        </div>
                    `;
                });
            }
            
            // Display Stack Overflow questions
            if (data.sources && data.sources.stackoverflow && data.sources.stackoverflow.questions) {
                const soQuestions = data.sources.stackoverflow.questions;
                soQuestions.forEach(q => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">💻 ${q.title}</div>
                            <div class="developer-company">by ${q.author}</div>
                            <div class="developer-location">⬆️ ${q.score} score • 💬 ${q.answers} answers • 👁️ ${q.views} views</div>
                            <div class="developer-location">🏷️ ${q.tags.join(', ')}</div>
                            <div class="developer-location">🔗 <a href="${q.url}" target="_blank">View Question</a></div>
                        </div>
                    `;
                });
            }
            
            // Display Medium articles
            if (data.sources && data.sources.medium && data.sources.medium.articles) {
                const articles = data.sources.medium.articles;
                articles.forEach(article => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">📝 ${article.title}</div>
                            <div class="developer-company">by ${article.author}</div>
                            <div class="developer-location">${article.summary}</div>
                            <div class="developer-location">📅 ${article.published}</div>
                            <div class="developer-location">🔗 <a href="${article.url}" target="_blank">Read Article</a></div>
                        </div>
                    `;
                });
            }
            
            // Display Product Hunt products
            if (data.sources && data.sources.producthunt && data.sources.producthunt.products) {
                const products = data.sources.producthunt.products;
                products.forEach(product => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">🚀 ${product.name}</div>
                            <div class="developer-company">${product.tagline}</div>
                            <div class="developer-location">by ${product.maker}</div>
                            <div class="developer-location">⬆️ ${product.votes} votes • 💬 ${product.comments} comments</div>
                            <div class="developer-location">🔗 <a href="${product.url}" target="_blank">View Product</a></div>
                        </div>
                    `;
                });
            }
            
            // Display Google Scholar papers
            if (data.sources && data.sources.scholar && data.sources.scholar.papers) {
                const papers = data.sources.scholar.papers;
                papers.forEach(paper => {
                    developersHtml += `
                        <div class="developer-card">
                            <div class="developer-name">🎓 ${paper.title}</div>
                            <div class="developer-company">by ${paper.authors}</div>
                            <div class="developer-location">📚 ${paper.journal} (${paper.year})</div>
                            <div class="developer-location">📊 ${paper.citations} citations</div>
                            <div class="developer-location">🔗 <a href="${paper.url}" target="_blank">View Paper</a></div>
                        </div>
                    `;
                });
            }
            
            // If no developers found, show a helpful message
            if (!developersHtml) {
                developersHtml = '<div class="loading">No developers found. Try searching for "react", "javascript", "python", or other programming terms.</div>';
            }
            
            document.getElementById('developersContent').innerHTML = developersHtml;
            
            // Display raw data
            let rawHtml = '<pre style="background: #f8f9fa; padding: 20px; border-radius: 8px; overflow-x: auto;">';
            rawHtml += JSON.stringify(data, null, 2);
            rawHtml += '</pre>';
            document.getElementById('rawContent').innerHTML = rawHtml;
        }
        
        // Export functionality
        document.getElementById('exportBtn').addEventListener('click', () => {
            if (currentResults) {
                // Simple CSV export
                let csv = 'Source,Name,Title,Company,Location,Email,Phone,Profile URL\\n';
                
                if (currentResults.formatted_sources && currentResults.formatted_sources.apollo && currentResults.formatted_sources.apollo.contacts) {
                    currentResults.formatted_sources.apollo.contacts.forEach(contact => {
                        csv += `Apollo.io,"${contact.name}","${contact.title}","${contact.company}","${contact.location}","${contact.email}","${contact.phone}","${contact.linkedin_url}"\\n`;
                    });
                }
                
                if (currentResults.formatted_sources && currentResults.formatted_sources.github && currentResults.formatted_sources.github.developers) {
                    currentResults.formatted_sources.github.developers.forEach(dev => {
                        csv += `GitHub,"${dev.name || dev.username}","Developer","${dev.company || 'Independent'}","${dev.location || 'Unknown'}","N/A","N/A","${dev.profile_url}"\\n`;
                    });
                }
                
                const blob = new Blob([csv], { type: 'text/csv' });
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'scraper_results.csv';
                a.click();
                window.URL.revokeObjectURL(url);
            }
        });
        
        // Load stats on page load
        loadStats();
    </script>
</body>
</html>
    ''')

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '')
        search_type = data.get('searchType', 'all')
        
        if not query:
            return jsonify({"error": "Query is required"})
        
        results = scraper.run_comprehensive_search(query, search_type)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/export/<search_id>')
def export_results(search_id):
    """Export search results to CSV"""
    try:
        # For now, export the latest search results
        if scraper.search_history:
            latest_search = scraper.search_history[-1]
            # This is a simplified export - in a real app you'd store results by ID
            return "Export functionality - CSV download would be implemented here"
        return jsonify({"error": "No search results to export"})
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/history')
def search_history():
    """Get search history"""
    return jsonify({
        "history": scraper.search_history[-10:],  # Last 10 searches
        "total_searches": len(scraper.search_history)
    })

@app.route('/stats')
def stats():
    """Get scraper statistics"""
    total_contacts = sum(
        len(data.get("contacts", [])) 
        for search in scraper.search_history 
        for data in [search.get("formatted_sources", {})] 
        if isinstance(data, dict)
    )
    
    total_developers = sum(
        len(data.get("developers", [])) 
        for search in scraper.search_history 
        for data in [search.get("formatted_sources", {})] 
        if isinstance(data, dict)
    )
    
    return jsonify({
        "total_searches": len(scraper.search_history),
        "total_contacts_found": total_contacts,
        "total_developers_found": total_developers,
        "apollo_api_configured": APOLLO_API_KEY != "your_apollo_key_here"
    })

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting Easy Scraper...")
    print("📱 Open your browser and go to: http://localhost:5004")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5004)
