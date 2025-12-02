#!/usr/bin/env python3
"""
Real LinkedIn-Style Lead Generator
Uses legitimate APIs and methods to find professional contacts
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
CORS(app)

# Professional Lead Generation APIs
HUNTER_API_KEY = "8c91a296393dcf910f13d0debb01ee58286927a0"  # Hunter.io API key
CLEARBIT_API_KEY = "your_clearbit_key_here"  # Get free at clearbit.com
SCRAPINGBEE_API_KEY = "1DF3YNRNHU5IJ295DZSRVKWHEEP0C6AZXLE0HI6KP1O87LLUEQ88K3CFKPHE1F1IQAJ1XZPF1POKE2RK"  # ScrapingBee API key

class RealLeadsGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def search_hunter_contacts(self, domain, limit=10):
        """Find contacts using Hunter.io API"""
        try:
            url = "https://api.hunter.io/v2/domain-search"
            params = {
                "domain": domain,
                "api_key": HUNTER_API_KEY,
                "limit": limit
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                contacts = []
                for email in data.get("data", {}).get("emails", []):
                    contacts.append({
                        "email": email.get("value", ""),
                        "first_name": email.get("first_name", ""),
                        "last_name": email.get("last_name", ""),
                        "position": email.get("position", ""),
                        "department": email.get("department", ""),
                        "confidence": email.get("confidence", 0),
                        "sources": email.get("sources", [])
                    })
                
                return {
                    "contacts": contacts,
                    "total": len(contacts),
                    "domain": domain,
                    "note": "Hunter.io - Professional email finder"
                }
            else:
                return {"error": f"Hunter.io API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Hunter.io search failed: {str(e)}"}
    
    def search_clearbit_enrichment(self, email):
        """Enrich contact data using Clearbit"""
        try:
            url = f"https://person.clearbit.com/v2/people/find"
            params = {"email": email}
            headers = {"Authorization": f"Bearer {CLEARBIT_API_KEY}"}
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name", {}).get("fullName", ""),
                    "email": data.get("email", ""),
                    "company": data.get("employment", {}).get("name", ""),
                    "title": data.get("employment", {}).get("title", ""),
                    "location": data.get("location", ""),
                    "linkedin": data.get("linkedin", {}).get("handle", ""),
                    "twitter": data.get("twitter", {}).get("handle", ""),
                    "bio": data.get("bio", ""),
                    "avatar": data.get("avatar", "")
                }
            else:
                return {"error": f"Clearbit API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Clearbit enrichment failed: {str(e)}"}
    
    def search_github_professionals(self, query, limit=20, min_followers=100, min_repos=10):
        """Find high-quality professional developers with detailed profiles"""
        try:
            # Enhanced search with quality filters
            search_query = f"{query} type:user"
            url = "https://api.github.com/search/users"
            params = {
                "q": search_query,
                "per_page": limit,
                "sort": "followers"
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                professionals = []
                
                for user in data.get("items", []):
                    try:
                        # Get detailed profile
                        profile_url = user.get("url")
                        if profile_url:
                            profile_response = requests.get(profile_url)
                            if profile_response.status_code == 200:
                                profile_data = profile_response.json()
                                
                                # Apply quality filters
                                if profile_data.get("followers", 0) < min_followers or profile_data.get("public_repos", 0) < min_repos:
                                    continue
                                
                                # Get repositories to find company info
                                repos_url = profile_data.get("repos_url")
                                company_info = ""
                                if repos_url:
                                    repos_response = requests.get(f"{repos_url}?per_page=5")
                                    if repos_response.status_code == 200:
                                        repos = repos_response.json()
                                        companies = set()
                                        for repo in repos:
                                            if repo.get("owner", {}).get("type") == "Organization":
                                                companies.add(repo.get("owner", {}).get("login"))
                                        if companies:
                                            company_info = ", ".join(list(companies)[:3])
                                
                                # Calculate lead quality score
                                quality_score = self.calculate_lead_score(profile_data, company_info)
                                
                                professionals.append({
                                    "name": profile_data.get("name", profile_data.get("login", "")),
                                    "username": profile_data.get("login", ""),
                                    "email": profile_data.get("email", ""),
                                    "company": profile_data.get("company", company_info),
                                    "location": profile_data.get("location", ""),
                                    "followers": profile_data.get("followers", 0),
                                    "following": profile_data.get("following", 0),
                                    "public_repos": profile_data.get("public_repos", 0),
                                    "bio": profile_data.get("bio", ""),
                                    "blog": profile_data.get("blog", ""),
                                    "twitter": profile_data.get("twitter_username", ""),
                                    "linkedin": "",  # GitHub doesn't provide LinkedIn
                                    "profile_url": profile_data.get("html_url", ""),
                                    "avatar_url": profile_data.get("avatar_url", ""),
                                    "hireable": profile_data.get("hireable", False),
                                    "created_at": profile_data.get("created_at", ""),
                                    "updated_at": profile_data.get("updated_at", ""),
                                    "quality_score": quality_score,
                                    "seniority_level": self.determine_seniority(profile_data),
                                    "tech_stack": self.extract_tech_stack(profile_data.get("bio", "")),
                                    "verified_email": bool(profile_data.get("email")),
                                    "verified_company": bool(profile_data.get("company"))
                                })
                    except Exception as e:
                        print(f"Error processing user {user.get('login', 'unknown')}: {e}")
                        continue
                
                return {
                    "professionals": professionals,
                    "total_count": data.get("total_count", 0),
                    "note": "GitHub API - Real developer profiles"
                }
            else:
                return {"error": f"GitHub API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"GitHub search failed: {str(e)}"}
    
    def calculate_lead_score(self, profile_data, company_info):
        """Calculate lead quality score based on multiple factors"""
        score = 0
        
        # Followers score (0-30 points)
        followers = profile_data.get("followers", 0)
        if followers >= 1000:
            score += 30
        elif followers >= 500:
            score += 25
        elif followers >= 100:
            score += 20
        elif followers >= 50:
            score += 15
        elif followers >= 10:
            score += 10
        
        # Repository count (0-20 points)
        repos = profile_data.get("public_repos", 0)
        if repos >= 50:
            score += 20
        elif repos >= 20:
            score += 15
        elif repos >= 10:
            score += 10
        elif repos >= 5:
            score += 5
        
        # Company presence (0-25 points)
        if profile_data.get("company"):
            score += 25
        elif company_info:
            score += 15
        
        # Email verification (0-15 points)
        if profile_data.get("email"):
            score += 15
        
        # Bio quality (0-10 points)
        bio = profile_data.get("bio", "")
        if bio and len(bio) > 50:
            score += 10
        elif bio and len(bio) > 20:
            score += 5
        
        return min(score, 100)  # Cap at 100
    
    def determine_seniority(self, profile_data):
        """Determine seniority level based on profile data"""
        followers = profile_data.get("followers", 0)
        repos = profile_data.get("public_repos", 0)
        bio = profile_data.get("bio", "").lower()
        
        # Check bio for seniority indicators
        if any(word in bio for word in ["senior", "lead", "principal", "architect", "director", "cto", "vp"]):
            return "Senior"
        elif any(word in bio for word in ["staff", "manager", "head"]):
            return "Staff"
        elif followers >= 1000 or repos >= 50:
            return "Senior"
        elif followers >= 100 or repos >= 10:
            return "Mid"
        else:
            return "Junior"
    
    def extract_tech_stack(self, bio):
        """Extract technology stack from bio"""
        tech_keywords = {
            "javascript": ["javascript", "js", "node", "react", "vue", "angular"],
            "python": ["python", "django", "flask", "fastapi"],
            "java": ["java", "spring", "maven"],
            "csharp": ["c#", "csharp", ".net", "dotnet"],
            "go": ["go", "golang"],
            "rust": ["rust"],
            "php": ["php", "laravel", "symfony"],
            "ruby": ["ruby", "rails"],
            "swift": ["swift", "ios"],
            "kotlin": ["kotlin", "android"],
            "typescript": ["typescript", "ts"],
            "docker": ["docker", "container"],
            "kubernetes": ["kubernetes", "k8s"],
            "aws": ["aws", "amazon web services"],
            "azure": ["azure", "microsoft azure"],
            "gcp": ["gcp", "google cloud"]
        }
        
        found_tech = []
        bio_lower = bio.lower()
        
        for tech, keywords in tech_keywords.items():
            if any(keyword in bio_lower for keyword in keywords):
                found_tech.append(tech)
        
        return found_tech[:5]  # Return top 5 technologies
    
    def calculate_stackoverflow_score(self, reputation, badges):
        """Calculate quality score for Stack Overflow users"""
        score = 0
        
        # Reputation score (0-40 points)
        if reputation >= 10000:
            score += 40
        elif reputation >= 5000:
            score += 35
        elif reputation >= 2000:
            score += 30
        elif reputation >= 1000:
            score += 25
        elif reputation >= 500:
            score += 20
        elif reputation >= 100:
            score += 15
        
        # Badge score (0-30 points)
        gold_badges = badges.get("gold", 0)
        silver_badges = badges.get("silver", 0)
        bronze_badges = badges.get("bronze", 0)
        
        score += min(gold_badges * 10, 20)  # Gold badges worth 10 points each, max 20
        score += min(silver_badges * 3, 15)  # Silver badges worth 3 points each, max 15
        score += min(bronze_badges * 1, 10)  # Bronze badges worth 1 point each, max 10
        
        return min(score, 100)  # Cap at 100
    
    def determine_stackoverflow_seniority(self, reputation, badges):
        """Determine seniority level for Stack Overflow users"""
        gold_badges = badges.get("gold", 0)
        
        if reputation >= 10000 or gold_badges >= 5:
            return "Expert"
        elif reputation >= 5000 or gold_badges >= 2:
            return "Senior"
        elif reputation >= 2000:
            return "Mid"
        elif reputation >= 1000:
            return "Junior"
        else:
            return "Beginner"
    
    def extract_expertise_tags(self, display_name):
        """Extract expertise tags from display name"""
        # This is a simple implementation - in reality you'd need to analyze their answers/tags
        expertise_keywords = {
            "javascript": ["js", "javascript", "node", "react", "vue", "angular"],
            "python": ["python", "django", "flask"],
            "java": ["java", "spring"],
            "csharp": ["c#", "csharp", ".net"],
            "php": ["php", "laravel"],
            "sql": ["sql", "mysql", "postgresql"],
            "css": ["css", "html", "frontend"],
            "devops": ["docker", "kubernetes", "aws", "azure"]
        }
        
        found_tags = []
        name_lower = display_name.lower()
        
        for tag, keywords in expertise_keywords.items():
            if any(keyword in name_lower for keyword in keywords):
                found_tags.append(tag)
        
        return found_tags[:3]  # Return top 3 expertise areas
    
    def search_stackoverflow_professionals(self, query, limit=10, min_reputation=1000):
        """Find professionals from Stack Overflow"""
        try:
            url = "https://api.stackexchange.com/2.3/users"
            params = {
                "order": "desc",
                "sort": "reputation",
                "inname": query,
                "site": "stackoverflow",
                "pagesize": limit * 2,  # Get more to filter by reputation
                "filter": "!6WPIom7QzJhJf"
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                professionals = []
                
                for user in data.get("items", []):
                    # Filter by minimum reputation
                    if user.get("reputation", 0) < min_reputation:
                        continue
                    
                    # Calculate quality score
                    reputation = user.get("reputation", 0)
                    badges = user.get("badge_counts", {})
                    quality_score = self.calculate_stackoverflow_score(reputation, badges)
                    
                    professionals.append({
                        "name": user.get("display_name", ""),
                        "user_id": user.get("user_id", ""),
                        "reputation": reputation,
                        "badges": {
                            "gold": badges.get("gold", 0),
                            "silver": badges.get("silver", 0),
                            "bronze": badges.get("bronze", 0)
                        },
                        "location": user.get("location", ""),
                        "website_url": user.get("website_url", ""),
                        "profile_url": user.get("link", ""),
                        "avatar_url": user.get("profile_image", ""),
                        "creation_date": user.get("creation_date", ""),
                        "last_access_date": user.get("last_access_date", ""),
                        "is_employee": user.get("is_employee", False),
                        "account_id": user.get("account_id", ""),
                        "quality_score": quality_score,
                        "seniority_level": self.determine_stackoverflow_seniority(reputation, badges),
                        "expertise_tags": self.extract_expertise_tags(user.get("display_name", ""))
                    })
                    
                    # Limit results
                    if len(professionals) >= limit:
                        break
                
                return {
                    "professionals": professionals,
                    "total": len(professionals),
                    "note": "Stack Overflow API - Developer community"
                }
            else:
                return {"error": f"Stack Overflow API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Stack Overflow search failed: {str(e)}"}
    
    def search_company_domains(self, company_name):
        """Find company domains and potential contacts"""
        try:
            # Use Clearbit's company API
            url = "https://company.clearbit.com/v2/companies/find"
            params = {"name": company_name}
            headers = {"Authorization": f"Bearer {CLEARBIT_API_KEY}"}
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name", ""),
                    "domain": data.get("domain", ""),
                    "description": data.get("description", ""),
                    "location": data.get("location", {}).get("city", ""),
                    "country": data.get("location", {}).get("country", ""),
                    "employees": data.get("metrics", {}).get("employees", 0),
                    "industry": data.get("category", {}).get("industry", ""),
                    "logo": data.get("logo", ""),
                    "website": data.get("domain", ""),
                    "note": "Clearbit Company API"
                }
            else:
                return {"error": f"Clearbit Company API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Company search failed: {str(e)}"}
    
    def search_company_employees(self, domain, limit=10):
        """Find employees of a company using Hunter.io"""
        try:
            url = "https://api.hunter.io/v2/domain-search"
            params = {
                "domain": domain,
                "api_key": HUNTER_API_KEY,
                "limit": limit
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                employees = []
                for email in data.get("data", {}).get("emails", []):
                    employees.append({
                        "email": email.get("value", ""),
                        "first_name": email.get("first_name", ""),
                        "last_name": email.get("last_name", ""),
                        "position": email.get("position", ""),
                        "department": email.get("department", ""),
                        "confidence": email.get("confidence", 0),
                        "sources": email.get("sources", []),
                        "company": domain
                    })
                
                return {
                    "employees": employees,
                    "total": len(employees),
                    "domain": domain,
                    "note": "Hunter.io - Company employee finder"
                }
            else:
                return {"error": f"Hunter.io API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Employee search failed: {str(e)}"}
    
    def verify_email(self, email):
        """Verify email address using Hunter.io"""
        try:
            url = "https://api.hunter.io/v2/email-verifier"
            params = {
                "email": email,
                "api_key": HUNTER_API_KEY
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {
                    "email": email,
                    "valid": data.get("data", {}).get("result") == "deliverable",
                    "confidence": data.get("data", {}).get("score", 0),
                    "sources": data.get("data", {}).get("sources", []),
                    "note": "Hunter.io email verification"
                }
            else:
                return {"error": f"Hunter.io verification error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Email verification failed: {str(e)}"}
    
    def run_comprehensive_lead_search(self, query, search_type="all"):
        """Run comprehensive lead search across multiple sources"""
        results = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "sources": {},
            "formatted_sources": {}
        }
        
        if search_type in ["all", "github"]:
            print(f"🔍 Searching GitHub for high-quality professionals: {query}")
            github_results = self.search_github_professionals(query, min_followers=50, min_repos=5)
            results["sources"]["github"] = github_results
            
            if "professionals" in github_results:
                results["formatted_sources"]["github"] = {
                    "developers": github_results["professionals"],
                    "total_count": github_results.get("total_count", 0)
                }
        
        if search_type in ["all", "stackoverflow"]:
            print(f"🔍 Searching Stack Overflow for high-reputation professionals: {query}")
            so_results = self.search_stackoverflow_professionals(query, min_reputation=500)
            results["sources"]["stackoverflow"] = so_results
            
            if "professionals" in so_results:
                results["formatted_sources"]["stackoverflow"] = {
                    "developers": so_results["professionals"],
                    "total_count": so_results.get("total", 0)
                }
        
        if search_type in ["all", "company", "employees"] and "." in query:
            # Extract domain from query
            domain = query.replace("https://", "").replace("http://", "").replace("www.", "")
            if not domain.startswith("http"):
                domain = domain.split("/")[0].split("?")[0]
            
            print(f"🔍 Searching employees for: {domain}")
            employee_results = self.search_company_employees(domain)
            results["sources"]["employees"] = employee_results
            
            if "employees" in employee_results:
                results["formatted_sources"]["employees"] = {
                    "contacts": employee_results["employees"],
                    "total_count": employee_results.get("total", 0)
                }
            
            # Also try to get company info if Clearbit is available
            if CLEARBIT_API_KEY != "your_clearbit_key_here":
                print(f"🔍 Searching company info for: {domain}")
                company_results = self.search_company_domains(domain)
                results["sources"]["company"] = company_results
        
        return results

# Initialize the lead generator
lead_generator = RealLeadsGenerator()

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Real LinkedIn-Style Lead Generator</title>
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
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
            padding: 20px; 
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .header p {
            font-size: 1.2em;
            opacity: 0.9;
        }
        .search-container {
            background: white;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            margin-bottom: 30px;
        }
        .search-form {
            display: flex;
            gap: 15px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        .search-input {
            flex: 1;
            min-width: 200px;
            padding: 15px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .search-input:focus {
            outline: none;
            border-color: #667eea;
        }
        .search-type {
            padding: 15px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            background: white;
            min-width: 150px;
        }
        .search-btn {
            padding: 15px 30px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        .search-btn:hover {
            transform: translateY(-2px);
        }
        .search-btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 10px;
            text-align: center;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .stat-number {
            font-size: 2em;
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        .stat-label {
            color: #666;
            font-size: 0.9em;
        }
        .tabs {
            display: flex;
            background: white;
            border-radius: 10px 10px 0 0;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .tab {
            flex: 1;
            padding: 15px;
            background: #f8f9fa;
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: 600;
            transition: background 0.3s;
        }
        .tab.active {
            background: white;
            color: #667eea;
        }
        .tab-content {
            background: white;
            border-radius: 0 0 10px 10px;
            padding: 30px;
            min-height: 400px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }
        .result-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #667eea;
            transition: transform 0.2s;
        }
        .result-card:hover {
            transform: translateY(-2px);
        }
        .result-name {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        .result-details {
            color: #666;
            line-height: 1.6;
        }
        .result-link {
            color: #667eea;
            text-decoration: none;
            font-weight: 600;
        }
        .result-link:hover {
            text-decoration: underline;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .spinner {
            border: 4px solid #f3f3f3;
            border-top: 4px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        .export-btn {
            background: #28a745;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            margin-top: 20px;
            transition: background 0.3s;
        }
        .export-btn:hover {
            background: #218838;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .success {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Real LinkedIn-Style Lead Generator</h1>
            <p>Find professional contacts using legitimate APIs and methods</p>
        </div>
        
        <div class="search-container">
            <form class="search-form" id="searchForm">
                <input type="text" class="search-input" id="queryInput" placeholder="Search for high-quality professionals (e.g., 'senior javascript developers', 'react engineers', 'company.com')" required>
                <select class="search-type" id="searchType">
                    <option value="all">All Sources</option>
                    <option value="github">GitHub Only</option>
                    <option value="stackoverflow">Stack Overflow Only</option>
                    <option value="company">Company + Employees</option>
                    <option value="employees">Employees Only</option>
                </select>
                <button type="submit" class="search-btn" id="searchBtn">🔍 Search Leads</button>
            </form>
        </div>
        
        <div class="stats" id="stats">
            <div class="stat-card">
                <div class="stat-number" id="totalContacts">0</div>
                <div class="stat-label">Total Contacts</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalCompanies">0</div>
                <div class="stat-label">Companies Found</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalDevelopers">0</div>
                <div class="stat-label">Developers</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="lastSearch">-</div>
                <div class="stat-label">Last Search</div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('developers')">👨‍💻 Developers</button>
            <button class="tab" onclick="showTab('employees')">📧 Employees</button>
            <button class="tab" onclick="showTab('companies')">🏢 Companies</button>
            <button class="tab" onclick="showTab('raw')">📋 Raw Data</button>
        </div>
        
        <div class="tab-content">
            <div id="developers-tab" class="tab-panel">
                <div id="developersResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search for professionals to see results...</p>
                    </div>
                </div>
            </div>
            
            <div id="employees-tab" class="tab-panel" style="display: none;">
                <div id="employeesResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search for company employees to see results...</p>
                    </div>
                </div>
            </div>
            
            <div id="companies-tab" class="tab-panel" style="display: none;">
                <div id="companiesResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search for companies to see results...</p>
                    </div>
                </div>
            </div>
            
            <div id="raw-tab" class="tab-panel" style="display: none;">
                <div id="rawResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search to see raw API data...</p>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentResults = {};
        
        function showTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-panel').forEach(panel => {
                panel.style.display = 'none';
            });
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + '-tab').style.display = 'block';
            document.querySelector(`[onclick="showTab('${tabName}')"]`).classList.add('active');
        }
        
        function updateStats(results) {
            const githubDevs = results.formatted_sources?.github?.developers?.length || 0;
            const soDevs = results.formatted_sources?.stackoverflow?.developers?.length || 0;
            const employees = results.formatted_sources?.employees?.contacts?.length || 0;
            const companies = results.sources?.company ? 1 : 0;
            
            document.getElementById('totalContacts').textContent = githubDevs + soDevs + employees;
            document.getElementById('totalCompanies').textContent = companies;
            document.getElementById('totalDevelopers').textContent = githubDevs + soDevs;
            document.getElementById('lastSearch').textContent = new Date().toLocaleTimeString();
        }
        
        function displayResults(results) {
            currentResults = results;
            updateStats(results);
            
            // Display developers
            displayDevelopers(results);
            
            // Display employees
            displayEmployees(results);
            
            // Display companies
            displayCompanies(results);
            
            // Display raw data
            displayRawData(results);
        }
        
        function displayDevelopers(results) {
            const container = document.getElementById('developersResults');
            const githubDevs = results.formatted_sources?.github?.developers || [];
            const soDevs = results.formatted_sources?.stackoverflow?.developers || [];
            
            if (githubDevs.length === 0 && soDevs.length === 0) {
                container.innerHTML = '<div class="error">No developers found. Try searching for "javascript", "react", "python", etc.</div>';
                return;
            }
            
            let html = '<div class="success">✅ Found professional developers!</div>';
            
            if (githubDevs.length > 0) {
                html += '<h3>GitHub Developers</h3><div class="results-grid">';
                githubDevs.forEach(dev => {
                    const qualityColor = dev.quality_score >= 80 ? '#28a745' : dev.quality_score >= 60 ? '#ffc107' : '#dc3545';
                    html += `
                        <div class="result-card">
                            <div class="result-name">${dev.name || dev.username} 
                                <span style="background: ${qualityColor}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 10px;">
                                    ${dev.quality_score}/100
                                </span>
                            </div>
                            <div class="result-details">
                                <strong>Seniority:</strong> ${dev.seniority_level || 'N/A'}<br>
                                <strong>Username:</strong> ${dev.username}<br>
                                <strong>Company:</strong> ${dev.company || 'N/A'}<br>
                                <strong>Location:</strong> ${dev.location || 'N/A'}<br>
                                <strong>Followers:</strong> ${dev.followers.toLocaleString()}<br>
                                <strong>Repos:</strong> ${dev.public_repos}<br>
                                ${dev.tech_stack && dev.tech_stack.length > 0 ? `<strong>Tech Stack:</strong> ${dev.tech_stack.join(', ')}<br>` : ''}
                                ${dev.bio ? `<strong>Bio:</strong> ${dev.bio}<br>` : ''}
                                ${dev.email ? `<strong>Email:</strong> ${dev.email}<br>` : ''}
                                ${dev.twitter ? `<strong>Twitter:</strong> @${dev.twitter}<br>` : ''}
                                ${dev.verified_email ? '<span style="color: #28a745;">✓ Verified Email</span><br>' : ''}
                                ${dev.verified_company ? '<span style="color: #28a745;">✓ Verified Company</span><br>' : ''}
                                <a href="${dev.profile_url}" target="_blank" class="result-link">View Profile</a>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            if (soDevs.length > 0) {
                html += '<h3>Stack Overflow Professionals</h3><div class="results-grid">';
                soDevs.forEach(dev => {
                    const qualityColor = dev.quality_score >= 80 ? '#28a745' : dev.quality_score >= 60 ? '#ffc107' : '#dc3545';
                    html += `
                        <div class="result-card">
                            <div class="result-name">${dev.name} 
                                <span style="background: ${qualityColor}; color: white; padding: 2px 8px; border-radius: 12px; font-size: 12px; margin-left: 10px;">
                                    ${dev.quality_score}/100
                                </span>
                            </div>
                            <div class="result-details">
                                <strong>Seniority:</strong> ${dev.seniority_level || 'N/A'}<br>
                                <strong>Reputation:</strong> ${dev.reputation.toLocaleString()}<br>
                                <strong>Location:</strong> ${dev.location || 'N/A'}<br>
                                <strong>Badges:</strong> ${dev.badges.gold} gold, ${dev.badges.silver} silver, ${dev.badges.bronze} bronze<br>
                                ${dev.expertise_tags && dev.expertise_tags.length > 0 ? `<strong>Expertise:</strong> ${dev.expertise_tags.join(', ')}<br>` : ''}
                                ${dev.website_url ? `<strong>Website:</strong> <a href="${dev.website_url}" target="_blank" class="result-link">${dev.website_url}</a><br>` : ''}
                                <a href="${dev.profile_url}" target="_blank" class="result-link">View Profile</a>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            }
            
            container.innerHTML = html;
        }
        
        function displayEmployees(results) {
            const container = document.getElementById('employeesResults');
            const employees = results.formatted_sources?.employees?.contacts || [];
            
            if (employees.length === 0) {
                container.innerHTML = '<div class="error">No employees found. Try searching for a company domain like "google.com" or "microsoft.com"</div>';
                return;
            }
            
            let html = '<div class="success">✅ Found company employees with emails!</div>';
            html += '<div class="results-grid">';
            
            employees.forEach(emp => {
                html += `
                    <div class="result-card">
                        <div class="result-name">${emp.first_name} ${emp.last_name}</div>
                        <div class="result-details">
                            <strong>Email:</strong> ${emp.email}<br>
                            <strong>Position:</strong> ${emp.position || 'N/A'}<br>
                            <strong>Department:</strong> ${emp.department || 'N/A'}<br>
                            <strong>Company:</strong> ${emp.company}<br>
                            <strong>Confidence:</strong> ${emp.confidence}%<br>
                            <strong>Sources:</strong> ${emp.sources.length} sources<br>
                            <a href="mailto:${emp.email}" class="result-link">Send Email</a>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        function displayCompanies(results) {
            const container = document.getElementById('companiesResults');
            const company = results.sources?.company;
            
            if (!company || company.error) {
                container.innerHTML = '<div class="error">No company information found. Try searching for a company domain like "google.com"</div>';
                return;
            }
            
            let html = '<div class="success">✅ Company information found!</div>';
            html += `
                <div class="result-card">
                    <div class="result-name">${company.name}</div>
                    <div class="result-details">
                        <strong>Domain:</strong> ${company.domain}<br>
                        <strong>Industry:</strong> ${company.industry || 'N/A'}<br>
                        <strong>Location:</strong> ${company.location}, ${company.country}<br>
                        <strong>Employees:</strong> ${company.employees.toLocaleString()}<br>
                        <strong>Description:</strong> ${company.description}<br>
                        <a href="https://${company.domain}" target="_blank" class="result-link">Visit Website</a>
                    </div>
                </div>
            `;
            
            container.innerHTML = html;
        }
        
        function displayRawData(results) {
            const container = document.getElementById('rawResults');
            container.innerHTML = `
                <div class="success">✅ Raw API Response</div>
                <pre style="background: #f8f9fa; padding: 20px; border-radius: 8px; overflow-x: auto; font-size: 12px;">${JSON.stringify(results, null, 2)}</pre>
            `;
        }
        
        document.getElementById('searchForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const query = document.getElementById('queryInput').value.trim();
            const searchType = document.getElementById('searchType').value;
            const searchBtn = document.getElementById('searchBtn');
            
            if (!query) return;
            
            searchBtn.disabled = true;
            searchBtn.textContent = '🔍 Searching...';
            
            // Show loading in all tabs
            document.getElementById('developersResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching for professionals...</p></div>';
            document.getElementById('employeesResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching for employees...</p></div>';
            document.getElementById('companiesResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching for companies...</p></div>';
            document.getElementById('rawResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Fetching raw data...</p></div>';
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query, searchType })
                });
                
                const results = await response.json();
                displayResults(results);
                
            } catch (error) {
                console.error('Search error:', error);
                document.getElementById('developersResults').innerHTML = `<div class="error">Search failed: ${error.message}</div>`;
            } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = '🔍 Search Leads';
            }
        });
    </script>
</body>
</html>
    ''')

@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        query = data.get('query', '').strip()
        search_type = data.get('searchType', 'all')
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        results = lead_generator.run_comprehensive_lead_search(query, search_type)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Real Leads Generator"
    })

if __name__ == '__main__':
    print("🚀 Starting Real LinkedIn-Style Lead Generator...")
    print("📱 Open your browser and go to: http://localhost:5005")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5005, debug=True)
