#!/usr/bin/env python3
"""
Premium Business Lead Generator
Focuses on real business contacts, executives, and decision makers
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

# Premium Lead Generation APIs
HUNTER_API_KEY = "8c91a296393dcf910f13d0debb01ee58286927a0"  # Hunter.io API key
SCRAPINGBEE_API_KEY = "1DF3YNRNHU5IJ295DZSRVKWHEEP0C6AZXLE0HI6KP1O87LLUEQ88K3CFKPHE1F1IQAJ1XZPF1POKE2RK"  # ScrapingBee API key

class PremiumLeadGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def search_company_executives(self, domain, limit=20):
        """Find executives and decision makers at companies"""
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
                executives = []
                
                for email in data.get("data", {}).get("emails", []):
                    # Include all contacts for executives tab
                    executives.append({
                            "email": email.get("value", ""),
                            "first_name": email.get("first_name", ""),
                            "last_name": email.get("last_name", ""),
                            "position": email.get("position", ""),
                            "department": email.get("department", ""),
                            "confidence": email.get("confidence", 0),
                            "sources": email.get("sources", []),
                            "company": domain,
                            "seniority_level": self.determine_seniority_level(position),
                            "lead_score": self.calculate_executive_score(email),
                            "verified": email.get("confidence", 0) >= 80
                        })
                
                return {
                    "executives": executives,
                    "total": len(executives),
                    "domain": domain,
                    "note": "Hunter.io - Executive contacts"
                }
            else:
                return {"error": f"Hunter.io API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Executive search failed: {str(e)}"}
    
    def search_company_contacts(self, domain, limit=50):
        """Find all company contacts with emails"""
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
                        "sources": email.get("sources", []),
                        "company": domain,
                        "seniority_level": self.determine_seniority_level(email.get("position", "")),
                        "lead_score": self.calculate_contact_score(email),
                        "verified": email.get("confidence", 0) >= 80
                    })
                
                return {
                    "contacts": contacts,
                    "total": len(contacts),
                    "domain": domain,
                    "note": "Hunter.io - Company contacts"
                }
            else:
                return {"error": f"Hunter.io API error: {response.status_code}"}
        except Exception as e:
            return {"error": f"Contact search failed: {str(e)}"}
    
    def verify_email_address(self, email):
        """Verify email address deliverability"""
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
    
    def search_by_industry(self, industry, location="", limit=20):
        """Search for companies in specific industries"""
        try:
            # This would typically use a company database API
            # For now, we'll use a mock approach with known companies
            industry_companies = {
                "technology": ["microsoft.com", "google.com", "apple.com", "amazon.com", "meta.com"],
                "finance": ["jpmorgan.com", "goldmansachs.com", "morganstanley.com", "wellsfargo.com"],
                "healthcare": ["pfizer.com", "johnsonandjohnson.com", "merck.com", "abbott.com"],
                "retail": ["walmart.com", "target.com", "homedepot.com", "costco.com"],
                "automotive": ["tesla.com", "ford.com", "gm.com", "toyota.com"]
            }
            
            companies = industry_companies.get(industry.lower(), [])
            all_contacts = []
            
            for company in companies[:3]:  # Limit to 3 companies per industry
                contacts = self.search_company_executives(company, limit=5)
                if "executives" in contacts:
                    all_contacts.extend(contacts["executives"])
            
            return {
                "contacts": all_contacts,
                "total": len(all_contacts),
                "industry": industry,
                "note": f"Industry search: {industry}"
            }
        except Exception as e:
            return {"error": f"Industry search failed: {str(e)}"}
    
    def determine_seniority_level(self, position):
        """Determine seniority level from position title"""
        position_lower = position.lower()
        
        if any(title in position_lower for title in ["ceo", "cto", "cfo", "cmo", "president", "founder"]):
            return "C-Level"
        elif any(title in position_lower for title in ["vp", "vice president", "director", "head of"]):
            return "VP/Director"
        elif any(title in position_lower for title in ["manager", "senior", "lead", "principal"]):
            return "Manager/Senior"
        elif any(title in position_lower for title in ["analyst", "coordinator", "specialist"]):
            return "Individual Contributor"
        else:
            return "Other"
    
    def calculate_executive_score(self, email_data):
        """Calculate lead score for executives"""
        score = 0
        
        # Position score (0-40 points)
        position = email_data.get("position", "").lower()
        if any(title in position for title in ["ceo", "cto", "cfo", "cmo", "president"]):
            score += 40
        elif any(title in position for title in ["vp", "vice president", "director"]):
            score += 35
        elif any(title in position for title in ["manager", "head", "lead"]):
            score += 25
        elif any(title in position for title in ["senior"]):
            score += 20
        
        # Confidence score (0-30 points)
        confidence = email_data.get("confidence", 0)
        score += min(confidence * 0.3, 30)
        
        # Department score (0-20 points)
        department = email_data.get("department", "").lower()
        if any(dept in department for dept in ["sales", "marketing", "business development"]):
            score += 20
        elif any(dept in department for dept in ["engineering", "product", "operations"]):
            score += 15
        elif any(dept in department for dept in ["finance", "hr", "legal"]):
            score += 10
        
        # Sources score (0-10 points)
        sources = email_data.get("sources", [])
        score += min(len(sources) * 2, 10)
        
        return min(score, 100)
    
    def calculate_contact_score(self, email_data):
        """Calculate lead score for general contacts"""
        score = 0
        
        # Position score (0-30 points)
        position = email_data.get("position", "").lower()
        if any(title in position for title in ["manager", "director", "head", "lead"]):
            score += 30
        elif any(title in position for title in ["senior", "principal"]):
            score += 25
        elif any(title in position for title in ["analyst", "coordinator", "specialist"]):
            score += 15
        
        # Confidence score (0-40 points)
        confidence = email_data.get("confidence", 0)
        score += min(confidence * 0.4, 40)
        
        # Department score (0-20 points)
        department = email_data.get("department", "").lower()
        if any(dept in department for dept in ["sales", "marketing", "business development"]):
            score += 20
        elif any(dept in department for dept in ["engineering", "product"]):
            score += 15
        elif any(dept in department for dept in ["customer success", "account management"]):
            score += 10
        
        # Sources score (0-10 points)
        sources = email_data.get("sources", [])
        score += min(len(sources) * 2, 10)
        
        return min(score, 100)
    
    def run_premium_lead_search(self, query, search_type="all"):
        """Run premium lead search focusing on business contacts"""
        results = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "sources": {},
            "formatted_sources": {}
        }
        
        if search_type in ["all", "company", "executives"] and "." in query:
            # Extract domain from query
            domain = query.replace("https://", "").replace("http://", "").replace("www.", "")
            if not domain.startswith("http"):
                domain = domain.split("/")[0].split("?")[0]
            
            print(f"🔍 Searching executives for: {domain}")
            print(f"🔍 Domain after extraction: '{domain}'")
            executive_results = self.search_company_executives(domain)
            print(f"🔍 Executive results: {executive_results}")
            results["sources"]["executives"] = executive_results
            
            if "executives" in executive_results:
                results["formatted_sources"]["executives"] = {
                    "contacts": executive_results["executives"],
                    "total_count": executive_results.get("total", 0)
                }
        
        if search_type in ["all", "company", "contacts"] and "." in query:
            # Extract domain from query
            domain = query.replace("https://", "").replace("http://", "").replace("www.", "")
            if not domain.startswith("http"):
                domain = domain.split("/")[0].split("?")[0]
            
            print(f"🔍 Searching all contacts for: {domain}")
            contact_results = self.search_company_contacts(domain)
            results["sources"]["contacts"] = contact_results
            
            if "contacts" in contact_results:
                results["formatted_sources"]["contacts"] = {
                    "contacts": contact_results["contacts"],
                    "total_count": contact_results.get("total", 0)
                }
        
        if search_type in ["all", "industry"] and not "." in query:
            print(f"🔍 Searching industry: {query}")
            industry_results = self.search_by_industry(query)
            results["sources"]["industry"] = industry_results
            
            if "contacts" in industry_results:
                results["formatted_sources"]["industry"] = {
                    "contacts": industry_results["contacts"],
                    "total_count": industry_results.get("total", 0)
                }
        
        return results

# Initialize the premium lead generator
lead_generator = PremiumLeadGenerator()

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Premium Business Lead Generator</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: #333;
        }
        .container { 
            max-width: 1400px; 
            margin: 0 auto; 
            padding: 20px; 
        }
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
        }
        .header h1 {
            font-size: 3em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        .header p {
            font-size: 1.3em;
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
            min-width: 300px;
            padding: 15px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        .search-input:focus {
            outline: none;
            border-color: #1e3c72;
        }
        .search-type {
            padding: 15px;
            border: 2px solid #e1e5e9;
            border-radius: 10px;
            font-size: 16px;
            background: white;
            min-width: 200px;
        }
        .search-btn {
            padding: 15px 30px;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
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
            color: #1e3c72;
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
            color: #1e3c72;
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
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
        }
        .result-card {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #1e3c72;
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
            color: #1e3c72;
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
            border-top: 4px solid #1e3c72;
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
        .quality-badge {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            margin-left: 10px;
        }
        .quality-high { background: #28a745; color: white; }
        .quality-medium { background: #ffc107; color: black; }
        .quality-low { background: #dc3545; color: white; }
        .seniority-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            margin-left: 5px;
        }
        .c-level { background: #6f42c1; color: white; }
        .vp-director { background: #fd7e14; color: white; }
        .manager { background: #20c997; color: white; }
        .individual { background: #6c757d; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎯 Premium Business Lead Generator</h1>
            <p>Find executives, decision makers, and business contacts with verified emails</p>
        </div>
        
        <div class="search-container">
            <form class="search-form" id="searchForm">
                <input type="text" class="search-input" id="queryInput" placeholder="Search for companies (e.g., 'microsoft.com', 'google.com') or industries (e.g., 'technology', 'finance')" required>
                <select class="search-type" id="searchType">
                    <option value="all">All Contacts</option>
                    <option value="executives">Executives Only</option>
                    <option value="contacts">All Contacts</option>
                    <option value="industry">Industry Search</option>
                </select>
                <button type="submit" class="search-btn" id="searchBtn">🔍 Find Business Leads</button>
            </form>
        </div>
        
        <div class="stats" id="stats">
            <div class="stat-card">
                <div class="stat-number" id="totalContacts">0</div>
                <div class="stat-label">Total Contacts</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalExecutives">0</div>
                <div class="stat-label">Executives</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="verifiedEmails">0</div>
                <div class="stat-label">Verified Emails</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="lastSearch">-</div>
                <div class="stat-label">Last Search</div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('executives')">👔 Executives</button>
            <button class="tab" onclick="showTab('contacts')">📧 All Contacts</button>
            <button class="tab" onclick="showTab('industry')">🏢 Industry</button>
            <button class="tab" onclick="showTab('raw')">📋 Raw Data</button>
        </div>
        
        <div class="tab-content">
            <div id="executives-tab" class="tab-panel">
                <div id="executivesResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search for company executives to see results...</p>
                    </div>
                </div>
            </div>
            
            <div id="contacts-tab" class="tab-panel" style="display: none;">
                <div id="contactsResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search for company contacts to see results...</p>
                    </div>
                </div>
            </div>
            
            <div id="industry-tab" class="tab-panel" style="display: none;">
                <div id="industryResults">
                    <div class="loading">
                        <div class="spinner"></div>
                        <p>Search by industry to see results...</p>
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
            const executives = results.formatted_sources?.executives?.contacts?.length || 0;
            const contacts = results.formatted_sources?.contacts?.contacts?.length || 0;
            const industry = results.formatted_sources?.industry?.contacts?.length || 0;
            
            const totalContacts = executives + contacts + industry;
            const verifiedEmails = [...(results.formatted_sources?.executives?.contacts || []), 
                                  ...(results.formatted_sources?.contacts?.contacts || []),
                                  ...(results.formatted_sources?.industry?.contacts || [])]
                                  .filter(contact => contact.verified).length;
            
            document.getElementById('totalContacts').textContent = totalContacts;
            document.getElementById('totalExecutives').textContent = executives;
            document.getElementById('verifiedEmails').textContent = verifiedEmails;
            document.getElementById('lastSearch').textContent = new Date().toLocaleTimeString();
        }
        
        function displayResults(results) {
            currentResults = results;
            updateStats(results);
            
            // Display executives
            displayExecutives(results);
            
            // Display contacts
            displayContacts(results);
            
            // Display industry
            displayIndustry(results);
            
            // Display raw data
            displayRawData(results);
        }
        
        function displayExecutives(results) {
            const container = document.getElementById('executivesResults');
            const executives = results.formatted_sources?.executives?.contacts || [];
            
            if (executives.length === 0) {
                container.innerHTML = '<div class="error">No executives found. Try searching for a company domain like "microsoft.com" or "google.com"</div>';
                return;
            }
            
            let html = '<div class="success">✅ Found company executives!</div>';
            html += '<div class="results-grid">';
            
            executives.forEach(exec => {
                const qualityClass = exec.lead_score >= 80 ? 'quality-high' : exec.lead_score >= 60 ? 'quality-medium' : 'quality-low';
                const seniorityClass = exec.seniority_level.toLowerCase().replace('/', '-').replace(' ', '-');
                
                html += `
                    <div class="result-card">
                        <div class="result-name">
                            ${exec.first_name} ${exec.last_name}
                            <span class="quality-badge ${qualityClass}">${exec.lead_score}/100</span>
                            <span class="seniority-badge ${seniorityClass}">${exec.seniority_level}</span>
                        </div>
                        <div class="result-details">
                            <strong>Email:</strong> ${exec.email}<br>
                            <strong>Position:</strong> ${exec.position}<br>
                            <strong>Department:</strong> ${exec.department || 'N/A'}<br>
                            <strong>Company:</strong> ${exec.company}<br>
                            <strong>Confidence:</strong> ${exec.confidence}%<br>
                            <strong>Sources:</strong> ${exec.sources.length} sources<br>
                            ${exec.verified ? '<span style="color: #28a745;">✓ Verified Email</span><br>' : ''}
                            <a href="mailto:${exec.email}" class="result-link">Send Email</a>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        function displayContacts(results) {
            const container = document.getElementById('contactsResults');
            const contacts = results.formatted_sources?.contacts?.contacts || [];
            
            if (contacts.length === 0) {
                container.innerHTML = '<div class="error">No contacts found. Try searching for a company domain like "microsoft.com"</div>';
                return;
            }
            
            let html = '<div class="success">✅ Found company contacts!</div>';
            html += '<div class="results-grid">';
            
            contacts.forEach(contact => {
                const qualityClass = contact.lead_score >= 80 ? 'quality-high' : contact.lead_score >= 60 ? 'quality-medium' : 'quality-low';
                const seniorityClass = contact.seniority_level.toLowerCase().replace('/', '-').replace(' ', '-');
                
                html += `
                    <div class="result-card">
                        <div class="result-name">
                            ${contact.first_name} ${contact.last_name}
                            <span class="quality-badge ${qualityClass}">${contact.lead_score}/100</span>
                            <span class="seniority-badge ${seniorityClass}">${contact.seniority_level}</span>
                        </div>
                        <div class="result-details">
                            <strong>Email:</strong> ${contact.email}<br>
                            <strong>Position:</strong> ${contact.position}<br>
                            <strong>Department:</strong> ${contact.department || 'N/A'}<br>
                            <strong>Company:</strong> ${contact.company}<br>
                            <strong>Confidence:</strong> ${contact.confidence}%<br>
                            <strong>Sources:</strong> ${contact.sources.length} sources<br>
                            ${contact.verified ? '<span style="color: #28a745;">✓ Verified Email</span><br>' : ''}
                            <a href="mailto:${contact.email}" class="result-link">Send Email</a>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
            container.innerHTML = html;
        }
        
        function displayIndustry(results) {
            const container = document.getElementById('industryResults');
            const contacts = results.formatted_sources?.industry?.contacts || [];
            
            if (contacts.length === 0) {
                container.innerHTML = '<div class="error">No industry contacts found. Try searching for "technology", "finance", "healthcare", etc.</div>';
                return;
            }
            
            let html = '<div class="success">✅ Found industry contacts!</div>';
            html += '<div class="results-grid">';
            
            contacts.forEach(contact => {
                const qualityClass = contact.lead_score >= 80 ? 'quality-high' : contact.lead_score >= 60 ? 'quality-medium' : 'quality-low';
                const seniorityClass = contact.seniority_level.toLowerCase().replace('/', '-').replace(' ', '-');
                
                html += `
                    <div class="result-card">
                        <div class="result-name">
                            ${contact.first_name} ${contact.last_name}
                            <span class="quality-badge ${qualityClass}">${contact.lead_score}/100</span>
                            <span class="seniority-badge ${seniorityClass}">${contact.seniority_level}</span>
                        </div>
                        <div class="result-details">
                            <strong>Email:</strong> ${contact.email}<br>
                            <strong>Position:</strong> ${contact.position}<br>
                            <strong>Department:</strong> ${contact.department || 'N/A'}<br>
                            <strong>Company:</strong> ${contact.company}<br>
                            <strong>Confidence:</strong> ${contact.confidence}%<br>
                            <strong>Sources:</strong> ${contact.sources.length} sources<br>
                            ${contact.verified ? '<span style="color: #28a745;">✓ Verified Email</span><br>' : ''}
                            <a href="mailto:${contact.email}" class="result-link">Send Email</a>
                        </div>
                    </div>
                `;
            });
            
            html += '</div>';
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
            document.getElementById('executivesResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching for executives...</p></div>';
            document.getElementById('contactsResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching for contacts...</p></div>';
            document.getElementById('industryResults').innerHTML = '<div class="loading"><div class="spinner"></div><p>Searching industry...</p></div>';
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
                document.getElementById('executivesResults').innerHTML = `<div class="error">Search failed: ${error.message}</div>`;
            } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = '🔍 Find Business Leads';
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
        
        results = lead_generator.run_premium_lead_search(query, search_type)
        return jsonify(results)
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "Premium Business Lead Generator"
    })

if __name__ == '__main__':
    print("🚀 Starting Premium Business Lead Generator...")
    print("📱 Open your browser and go to: http://localhost:5006")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5006, debug=True)
