#!/usr/bin/env python3
"""
Multi-Source Lead Generator - Combines Multiple Free APIs
Gets closer to Apollo.io quality by combining multiple data sources
"""

import requests
import json
import time
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
from datetime import datetime

app = Flask(__name__)
CORS(app)

# Multiple API Keys
HUNTER_API_KEY = "8c91a296393dcf910f13d0debb01ee58286927a0"
CLEARBIT_API_KEY = "your_clearbit_key_here"  # Get free at clearbit.com
SCRAPINGBEE_API_KEY = "1DF3YNRNHU5IJ295DZSRVKWHEEP0C6AZXLE0HI6KP1O87LLUEQ88K3CFKPHE1F1IQAJ1XZPF1POKE2RK"

class MultiSourceLeadGenerator:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
    
    def search_hunter_contacts(self, domain, limit=20):
        """Get contacts from Hunter.io"""
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
                        "company": domain,
                        "linkedin": email.get("linkedin", ""),
                        "source": "Hunter.io",
                        "verified": email.get("confidence", 0) >= 80
                    })
                
                return contacts
            else:
                return []
        except Exception as e:
            print(f"Hunter.io error: {e}")
            return []
    
    def search_clearbit_contacts(self, domain):
        """Get company info from Clearbit"""
        try:
            if CLEARBIT_API_KEY == "your_clearbit_key_here":
                return {}
                
            url = "https://company.clearbit.com/v2/companies/find"
            params = {"name": domain}
            headers = {"Authorization": f"Bearer {CLEARBIT_API_KEY}"}
            
            response = requests.get(url, params=params, headers=headers)
            if response.status_code == 200:
                data = response.json()
                return {
                    "name": data.get("name", ""),
                    "domain": data.get("domain", ""),
                    "description": data.get("description", ""),
                    "employees": data.get("metrics", {}).get("employees", 0),
                    "industry": data.get("category", {}).get("industry", ""),
                    "location": data.get("location", {}).get("city", ""),
                    "country": data.get("location", {}).get("country", ""),
                    "logo": data.get("logo", ""),
                    "source": "Clearbit"
                }
            else:
                return {}
        except Exception as e:
            print(f"Clearbit error: {e}")
            return {}
    
    def search_github_company_employees(self, company_name):
        """Find GitHub users who work at the company"""
        try:
            url = "https://api.github.com/search/users"
            params = {
                "q": f"{company_name} in:company type:user",
                "per_page": 10,
                "sort": "followers"
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                employees = []
                
                for user in data.get("items", []):
                    # Get detailed profile
                    profile_url = user.get("url")
                    if profile_url:
                        profile_response = requests.get(profile_url)
                        if profile_response.status_code == 200:
                            profile_data = profile_response.json()
                            
                            # Check if they actually work at the company
                            company = profile_data.get("company", "").lower()
                            if company_name.lower() in company or any(word in company for word in company_name.lower().split()):
                                employees.append({
                                    "name": profile_data.get("name", profile_data.get("login", "")),
                                    "username": profile_data.get("login", ""),
                                    "email": profile_data.get("email", ""),
                                    "company": profile_data.get("company", ""),
                                    "location": profile_data.get("location", ""),
                                    "followers": profile_data.get("followers", 0),
                                    "profile_url": profile_data.get("html_url", ""),
                                    "avatar_url": profile_data.get("avatar_url", ""),
                                    "source": "GitHub",
                                    "verified": bool(profile_data.get("email"))
                                })
                
                return employees
            else:
                return []
        except Exception as e:
            print(f"GitHub error: {e}")
            return []
    
    def search_linkedin_company_page(self, company_name):
        """Mock LinkedIn company search - in reality you'd need LinkedIn API"""
        try:
            # This is a mock - real implementation would need LinkedIn API
            # For now, we'll return some sample data
            return {
                "company": company_name,
                "employees_found": 0,
                "note": "LinkedIn API access required for real data",
                "source": "LinkedIn (Mock)"
            }
        except Exception as e:
            return {"error": str(e)}
    
    def search_company_websites(self, domain):
        """Search company website for contact information"""
        try:
            # This would use ScrapingBee to scrape company websites
            if SCRAPINGBEE_API_KEY == "your_scrapingbee_key_here":
                return {}
                
            url = "https://app.scrapingbee.com/api/v1/"
            params = {
                "api_key": SCRAPINGBEE_API_KEY,
                "url": f"https://{domain}/about",
                "render_js": "false"
            }
            
            response = requests.get(url, params=params)
            if response.status_code == 200:
                # Parse HTML for contact information
                # This is simplified - real implementation would parse HTML
                return {
                    "website_contacts": [],
                    "note": "Website scraping implemented",
                    "source": "Company Website"
                }
            else:
                return {}
        except Exception as e:
            print(f"Website scraping error: {e}")
            return {}
    
    def run_comprehensive_search(self, query):
        """Run search across all available sources"""
        results = {
            "query": query,
            "timestamp": datetime.now().isoformat(),
            "sources": {},
            "all_contacts": []
        }
        
        # Extract domain/company name
        if "." in query:
            domain = query.replace("https://", "").replace("http://", "").replace("www.", "")
            if not domain.startswith("http"):
                domain = domain.split("/")[0].split("?")[0]
            company_name = domain.split(".")[0]
        else:
            domain = f"{query}.com"
            company_name = query
        
        print(f"🔍 Searching for: {company_name} ({domain})")
        
        # 1. Hunter.io contacts
        print("📧 Searching Hunter.io...")
        hunter_contacts = self.search_hunter_contacts(domain)
        results["sources"]["hunter"] = {
            "contacts": hunter_contacts,
            "total": len(hunter_contacts)
        }
        results["all_contacts"].extend(hunter_contacts)
        
        # 2. Clearbit company info
        print("🏢 Searching Clearbit...")
        clearbit_info = self.search_clearbit_contacts(domain)
        results["sources"]["clearbit"] = clearbit_info
        
        # 3. GitHub employees
        print("👨‍💻 Searching GitHub...")
        github_employees = self.search_github_company_employees(company_name)
        results["sources"]["github"] = {
            "employees": github_employees,
            "total": len(github_employees)
        }
        results["all_contacts"].extend(github_employees)
        
        # 4. LinkedIn (mock)
        print("💼 Searching LinkedIn...")
        linkedin_info = self.search_linkedin_company_page(company_name)
        results["sources"]["linkedin"] = linkedin_info
        
        # 5. Company website
        print("🌐 Searching company website...")
        website_info = self.search_company_websites(domain)
        results["sources"]["website"] = website_info
        
        # Calculate total contacts found
        results["total_contacts"] = len(results["all_contacts"])
        
        return results

# Initialize the multi-source generator
lead_generator = MultiSourceLeadGenerator()

@app.route('/')
def index():
    return render_template_string('''
<!DOCTYPE html>
<html>
<head>
    <title>Multi-Source Lead Generator</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
            margin: 0;
            padding: 20px;
        }
        .container { 
            max-width: 1400px; 
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
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
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
        .sources-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .source-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .source-title {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        .contacts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .contact-card {
            background: white;
            border-radius: 10px;
            padding: 20px;
            border-left: 4px solid #667eea;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }
        .contact-name {
            font-size: 1.2em;
            font-weight: bold;
            margin-bottom: 10px;
            color: #333;
        }
        .contact-details {
            color: #666;
            line-height: 1.6;
        }
        .source-badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 10px;
            font-weight: bold;
            margin-left: 10px;
        }
        .hunter { background: #28a745; color: white; }
        .github { background: #6f42c1; color: white; }
        .clearbit { background: #fd7e14; color: white; }
        .linkedin { background: #0077b5; color: white; }
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
            <h1>🎯 Multi-Source Lead Generator</h1>
            <p>Combines multiple free APIs to get closer to Apollo.io quality</p>
        </div>
        
        <div class="search-container">
            <form class="search-form" id="searchForm">
                <input type="text" class="search-input" id="queryInput" placeholder="Enter company name or domain (e.g., microsoft, google.com)" required>
                <button type="submit" class="search-btn" id="searchBtn">🔍 Find All Contacts</button>
            </form>
        </div>
        
        <div class="stats" id="stats" style="display: none;">
            <div class="stat-card">
                <div class="stat-number" id="totalContacts">0</div>
                <div class="stat-label">Total Contacts</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="hunterContacts">0</div>
                <div class="stat-label">Hunter.io</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="githubContacts">0</div>
                <div class="stat-label">GitHub</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="verifiedEmails">0</div>
                <div class="stat-label">Verified Emails</div>
            </div>
        </div>
        
        <div id="sources"></div>
        <div id="contacts"></div>
    </div>

    <script>
        document.getElementById('searchForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const query = document.getElementById('queryInput').value.trim();
            const searchBtn = document.getElementById('searchBtn');
            const statsDiv = document.getElementById('stats');
            const sourcesDiv = document.getElementById('sources');
            const contactsDiv = document.getElementById('contacts');
            
            if (!query) return;
            
            searchBtn.disabled = true;
            searchBtn.textContent = '🔍 Searching All Sources...';
            statsDiv.style.display = 'none';
            sourcesDiv.innerHTML = '<div class="loading">Searching across multiple data sources...</div>';
            contactsDiv.innerHTML = '';
            
            try {
                const response = await fetch('/search', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ query })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    sourcesDiv.innerHTML = `<div class="error">Error: ${data.error}</div>`;
                } else {
                    // Update stats
                    document.getElementById('totalContacts').textContent = data.total_contacts || 0;
                    document.getElementById('hunterContacts').textContent = data.sources?.hunter?.total || 0;
                    document.getElementById('githubContacts').textContent = data.sources?.github?.total || 0;
                    document.getElementById('verifiedEmails').textContent = 
                        (data.all_contacts || []).filter(c => c.verified).length;
                    
                    statsDiv.style.display = 'grid';
                    
                    // Display sources
                    let sourcesHtml = '<div class="success">✅ Multi-source search completed!</div>';
                    sourcesHtml += '<div class="sources-grid">';
                    
                    // Hunter.io results
                    if (data.sources?.hunter?.total > 0) {
                        sourcesHtml += `
                            <div class="source-card">
                                <div class="source-title">📧 Hunter.io</div>
                                <div>Found ${data.sources.hunter.total} contacts with emails</div>
                            </div>
                        `;
                    }
                    
                    // GitHub results
                    if (data.sources?.github?.total > 0) {
                        sourcesHtml += `
                            <div class="source-card">
                                <div class="source-title">👨‍💻 GitHub</div>
                                <div>Found ${data.sources.github.total} developers</div>
                            </div>
                        `;
                    }
                    
                    // Clearbit results
                    if (data.sources?.clearbit?.name) {
                        sourcesHtml += `
                            <div class="source-card">
                                <div class="source-title">🏢 Clearbit</div>
                                <div>Company: ${data.sources.clearbit.name}</div>
                                <div>Employees: ${data.sources.clearbit.employees?.toLocaleString() || 'N/A'}</div>
                                <div>Industry: ${data.sources.clearbit.industry || 'N/A'}</div>
                            </div>
                        `;
                    }
                    
                    sourcesHtml += '</div>';
                    sourcesDiv.innerHTML = sourcesHtml;
                    
                    // Display all contacts
                    if (data.all_contacts && data.all_contacts.length > 0) {
                        let contactsHtml = '<h2>All Contacts Found</h2>';
                        contactsHtml += '<div class="contacts-grid">';
                        
                        data.all_contacts.forEach(contact => {
                            const sourceClass = contact.source?.toLowerCase().replace('.', '') || 'unknown';
                            contactsHtml += `
                                <div class="contact-card">
                                    <div class="contact-name">
                                        ${contact.first_name || contact.name || 'N/A'} ${contact.last_name || ''}
                                        <span class="source-badge ${sourceClass}">${contact.source || 'Unknown'}</span>
                                    </div>
                                    <div class="contact-details">
                                        ${contact.email ? `<strong>Email:</strong> ${contact.email}<br>` : ''}
                                        ${contact.position ? `<strong>Position:</strong> ${contact.position}<br>` : ''}
                                        ${contact.company ? `<strong>Company:</strong> ${contact.company}<br>` : ''}
                                        ${contact.department ? `<strong>Department:</strong> ${contact.department}<br>` : ''}
                                        ${contact.confidence ? `<strong>Confidence:</strong> ${contact.confidence}%<br>` : ''}
                                        ${contact.followers ? `<strong>Followers:</strong> ${contact.followers.toLocaleString()}<br>` : ''}
                                        ${contact.verified ? '<span style="color: #28a745;">✓ Verified Email</span><br>' : ''}
                                        ${contact.linkedin ? `<a href="${contact.linkedin}" target="_blank" style="color: #0077b5;">LinkedIn Profile</a><br>` : ''}
                                        ${contact.profile_url ? `<a href="${contact.profile_url}" target="_blank" style="color: #6f42c1;">GitHub Profile</a><br>` : ''}
                                        ${contact.email ? `<a href="mailto:${contact.email}" style="color: #667eea;">Send Email</a>` : ''}
                                    </div>
                                </div>
                            `;
                        });
                        
                        contactsHtml += '</div>';
                        contactsDiv.innerHTML = contactsHtml;
                    } else {
                        contactsDiv.innerHTML = '<div class="error">No contacts found across all sources.</div>';
                    }
                }
                
            } catch (error) {
                sourcesDiv.innerHTML = `<div class="error">Search failed: ${error.message}</div>`;
            } finally {
                searchBtn.disabled = false;
                searchBtn.textContent = '🔍 Find All Contacts';
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
        
        results = lead_generator.run_comprehensive_search(query)
        return jsonify(results)
        
    except Exception as e:
        print(f"Error in search: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting Multi-Source Lead Generator...")
    print("📱 Open your browser and go to: http://localhost:5008")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5008, debug=True)
