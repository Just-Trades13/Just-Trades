#!/usr/bin/env python3
"""
Simple Premium Lead Generator - Working Version
"""

import requests
import json
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

HUNTER_API_KEY = "8c91a296393dcf910f13d0debb01ee58286927a0"

def search_company_contacts(domain, limit=20):
    """Find company contacts using Hunter.io"""
    try:
        url = "https://api.hunter.io/v2/domain-search"
        params = {
            "domain": domain,
            "api_key": HUNTER_API_KEY,
            "limit": limit
        }
        
        print(f"Making request to Hunter.io for domain: {domain}")
        response = requests.get(url, params=params)
        print(f"Response status: {response.status_code}")
        
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
                    "company": domain,
                    "linkedin": email.get("linkedin", ""),
                    "verified": email.get("confidence", 0) >= 80
                })
            
            return {
                "contacts": contacts,
                "total": len(contacts),
                "domain": domain
            }
        else:
            print(f"Hunter.io error: {response.status_code} - {response.text}")
            return {"error": f"Hunter.io API error: {response.status_code}"}
    except Exception as e:
        print(f"Exception: {e}")
        return {"error": f"Search failed: {str(e)}"}

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
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            color: #333;
            margin: 0;
            padding: 20px;
        }
        .container { 
            max-width: 1200px; 
            margin: 0 auto; 
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
        }
        .results-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .result-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #1e3c72;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
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
        .success {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .error {
            background: #f8d7da;
            color: #721c24;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
        }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
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
                <input type="text" class="search-input" id="queryInput" placeholder="Enter company domain (e.g., microsoft.com, google.com)" required>
                <button type="submit" class="search-btn" id="searchBtn">🔍 Find Business Leads</button>
            </form>
        </div>
        
        <div id="results"></div>
    </div>

    <script>
        document.getElementById('searchForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const query = document.getElementById('queryInput').value.trim();
            const searchBtn = document.getElementById('searchBtn');
            const resultsDiv = document.getElementById('results');
            
            if (!query) return;
            
            searchBtn.disabled = true;
            searchBtn.textContent = '🔍 Searching...';
            resultsDiv.innerHTML = '<div class="loading">Searching for business contacts...</div>';
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    resultsDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                } else if (data.contacts && data.contacts.length > 0) {
                    let html = `<div class="success">✅ Found ${data.contacts.length} business contacts!</div>`;
                    html += '<div class="results-grid">';
                    
                    data.contacts.forEach(contact => {
                        html += `
                            <div class="result-card">
                                <div class="result-name">${contact.first_name} ${contact.last_name}</div>
                                <div class="result-details">
                                    <strong>Email:</strong> ${contact.email}<br>
                                    <strong>Position:</strong> ${contact.position}<br>
                                    <strong>Department:</strong> ${contact.department || 'N/A'}<br>
                                    <strong>Company:</strong> ${contact.company}<br>
                                    <strong>Confidence:</strong> ${contact.confidence}%<br>
                                    ${contact.verified ? '<span style="color: #28a745;">✓ Verified Email</span><br>' : ''}
                                    ${contact.linkedin ? `<a href="${contact.linkedin}" target="_blank" class="result-link">LinkedIn Profile</a><br>` : ''}
                                    <a href="mailto:${contact.email}" class="result-link">Send Email</a>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += '</div>';
                    resultsDiv.innerHTML = html;
                } else {
                    resultsDiv.innerHTML = '<div class="error">No contacts found. Try a different company domain.</div>';
                }
                
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">Search failed: ${error.message}</div>`;
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
        
        if not query:
            return jsonify({"error": "Query is required"}), 400
        
        # Extract domain
        domain = query.replace("https://", "").replace("http://", "").replace("www.", "")
        if not domain.startswith("http"):
            domain = domain.split("/")[0].split("?")[0]
        
        print(f"Searching for domain: {domain}")
        results = search_company_contacts(domain)
        
        return jsonify(results)
        
    except Exception as e:
        print(f"Error in search: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Simple Premium Lead Generator...")
    print("📱 Open your browser and go to: http://localhost:5007")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5007, debug=True)
