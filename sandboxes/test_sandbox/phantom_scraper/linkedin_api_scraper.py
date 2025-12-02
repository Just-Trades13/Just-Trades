#!/usr/bin/env python3
"""
LinkedIn API Scraper - Official API Integration
Uses LinkedIn's official Lead Sync API instead of web scraping
"""

import requests
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# LinkedIn API Configuration
LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
API_VERSION = "202410"  # Latest version as per documentation

# HTML Template for LinkedIn API Interface
LINKEDIN_HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>LinkedIn API Scraper</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .form-group { margin: 20px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; color: #333; }
        input, textarea, select { width: 100%; padding: 12px; margin-bottom: 10px; border: 1px solid #ddd; border-radius: 5px; font-size: 14px; }
        button { background: #0077b5; color: white; padding: 12px 25px; border: none; cursor: pointer; border-radius: 5px; font-size: 16px; margin-right: 10px; }
        button:hover { background: #005885; }
        .result { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 5px; border-left: 4px solid #0077b5; }
        .error { background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; border-left: 4px solid #dc3545; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; border-left: 4px solid #28a745; }
        .api-info { background: #e3f2fd; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .tabs { display: flex; margin-bottom: 20px; }
        .tab { padding: 10px 20px; background: #f0f0f0; border: none; cursor: pointer; margin-right: 5px; }
        .tab.active { background: #0077b5; color: white; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 LinkedIn API Scraper</h1>
        <p>Official LinkedIn API integration - No web scraping needed!</p>
        
        <div class="api-info">
            <h3>📋 Setup Required:</h3>
            <ol>
                <li>Get LinkedIn Developer App credentials</li>
                <li>Request API permissions: <code>r_marketing_leadgen_automation</code>, <code>rw_ads</code>, <code>r_ads</code></li>
                <li>Generate access token</li>
                <li>Enter credentials below</li>
            </ol>
        </div>

        <div class="tabs">
            <button class="tab active" onclick="showTab('credentials')">🔑 Credentials</button>
            <button class="tab" onclick="showTab('leads')">👥 Lead Forms</button>
            <button class="tab" onclick="showTab('responses')">📊 Lead Responses</button>
            <button class="tab" onclick="showTab('events')">🎯 Events</button>
        </div>

        <!-- Credentials Tab -->
        <div id="credentials" class="tab-content active">
            <h3>API Credentials</h3>
            <form id="credentialsForm">
                <div class="form-group">
                    <label>Access Token:</label>
                    <input type="password" id="accessToken" placeholder="Enter your LinkedIn access token" required>
                </div>
                <div class="form-group">
                    <label>Organization ID (optional):</label>
                    <input type="text" id="orgId" placeholder="urn:li:organization:123456">
                </div>
                <button type="submit">🔗 Test Connection</button>
            </form>
            <div id="credentialsResult"></div>
        </div>

        <!-- Lead Forms Tab -->
        <div id="leads" class="tab-content">
            <h3>Lead Forms</h3>
            <form id="leadsForm">
                <div class="form-group">
                    <label>Owner Type:</label>
                    <select id="ownerType">
                        <option value="sponsoredAccount">Sponsored Account</option>
                        <option value="organization">Organization</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Owner ID:</label>
                    <input type="text" id="ownerId" placeholder="urn:li:sponsoredAccount:123456 or urn:li:organization:123456">
                </div>
                <button type="submit">📋 Get Lead Forms</button>
            </form>
            <div id="leadsResult"></div>
        </div>

        <!-- Lead Responses Tab -->
        <div id="responses" class="tab-content">
            <h3>Lead Responses</h3>
            <form id="responsesForm">
                <div class="form-group">
                    <label>Lead Form ID:</label>
                    <input type="text" id="formId" placeholder="urn:li:leadGenForm:123456">
                </div>
                <div class="form-group">
                    <label>Max Results:</label>
                    <input type="number" id="maxResponses" value="10" min="1" max="100">
                </div>
                <button type="submit">📊 Get Lead Responses</button>
            </form>
            <div id="responsesResult"></div>
        </div>

        <!-- Events Tab -->
        <div id="events" class="tab-content">
            <h3>Events</h3>
            <form id="eventsForm">
                <div class="form-group">
                    <label>Organization ID:</label>
                    <input type="text" id="eventOrgId" placeholder="urn:li:organization:123456">
                </div>
                <div class="form-group">
                    <label>Max Results:</label>
                    <input type="number" id="maxEvents" value="10" min="1" max="100">
                </div>
                <button type="submit">🎯 Get Events</button>
            </form>
            <div id="eventsResult"></div>
        </div>
    </div>

    <script>
        let accessToken = '';
        
        function showTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName).classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
        }

        // Credentials form
        document.getElementById('credentialsForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            accessToken = document.getElementById('accessToken').value;
            
            const resultDiv = document.getElementById('credentialsResult');
            resultDiv.innerHTML = '<div class="result">🔄 Testing connection...</div>';
            
            try {
                const response = await fetch('/api/linkedin/test', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ accessToken: accessToken })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultDiv.innerHTML = `<div class="success">✅ Connection successful! API is ready to use.</div>`;
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Connection failed: ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            }
        });

        // Lead Forms form
        document.getElementById('leadsForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('leadsResult');
            resultDiv.innerHTML = '<div class="result">🔄 Fetching lead forms...</div>';
            
            try {
                const response = await fetch('/api/linkedin/lead-forms', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        accessToken: accessToken,
                        ownerType: document.getElementById('ownerType').value,
                        ownerId: document.getElementById('ownerId').value
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="success">✅ Found ${data.forms.length} lead forms</div>
                        <pre>${JSON.stringify(data.forms, null, 2)}</pre>
                    `;
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Error: ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            }
        });

        // Lead Responses form
        document.getElementById('responsesForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('responsesResult');
            resultDiv.innerHTML = '<div class="result">🔄 Fetching lead responses...</div>';
            
            try {
                const response = await fetch('/api/linkedin/lead-responses', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        accessToken: accessToken,
                        formId: document.getElementById('formId').value,
                        maxResults: document.getElementById('maxResponses').value
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="success">✅ Found ${data.responses.length} lead responses</div>
                        <pre>${JSON.stringify(data.responses, null, 2)}</pre>
                    `;
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Error: ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            }
        });

        // Events form
        document.getElementById('eventsForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const resultDiv = document.getElementById('eventsResult');
            resultDiv.innerHTML = '<div class="result">🔄 Fetching events...</div>';
            
            try {
                const response = await fetch('/api/linkedin/events', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        accessToken: accessToken,
                        orgId: document.getElementById('eventOrgId').value,
                        maxResults: document.getElementById('maxEvents').value
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    resultDiv.innerHTML = `
                        <div class="success">✅ Found ${data.events.length} events</div>
                        <pre>${JSON.stringify(data.events, null, 2)}</pre>
                    `;
                } else {
                    resultDiv.innerHTML = `<div class="error">❌ Error: ${data.error}</div>`;
                }
            } catch (error) {
                resultDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            }
        });
    </script>
</body>
</html>
"""

class LinkedInAPIClient:
    def __init__(self, access_token):
        self.access_token = access_token
        self.base_url = LINKEDIN_API_BASE
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'LinkedIn-Version': API_VERSION,
            'X-Restli-Protocol-Version': '2.0.0',
            'Content-Type': 'application/json'
        }
    
    def test_connection(self):
        """Test API connection"""
        try:
            response = requests.get(f"{self.base_url}/me", headers=self.headers)
            if response.status_code == 200:
                return {"success": True, "data": response.json()}
            else:
                return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_lead_forms(self, owner_type, owner_id):
        """Get lead forms using the new Lead Sync API"""
        try:
            # Use the new /leadForms endpoint
            params = {
                'owner': f'urn:li:{owner_type}:{owner_id.split(":")[-1]}',
                'fields': 'id,name,state,creationLocale,content,owner'
            }
            
            response = requests.get(f"{self.base_url}/leadForms", 
                                  headers=self.headers, 
                                  params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "forms": data.get('elements', [])}
            else:
                return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_lead_responses(self, form_id, max_results=10):
        """Get lead responses using the new Lead Sync API"""
        try:
            # Use the new /leadFormResponses endpoint
            params = {
                'leadGenForm': form_id,
                'count': max_results,
                'fields': 'id,submittedAt,testLead,leadType,formResponse,form'
            }
            
            response = requests.get(f"{self.base_url}/leadFormResponses", 
                                  headers=self.headers, 
                                  params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "responses": data.get('elements', [])}
            else:
                return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_events(self, org_id, max_results=10):
        """Get events using the Events API"""
        try:
            params = {
                'organizer': org_id,
                'count': max_results,
                'fields': 'id,name,start,status,organizer'
            }
            
            response = requests.get(f"{self.base_url}/events", 
                                  headers=self.headers, 
                                  params=params)
            
            if response.status_code == 200:
                data = response.json()
                return {"success": True, "events": data.get('elements', [])}
            else:
                return {"success": False, "error": f"API Error: {response.status_code} - {response.text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

@app.route('/')
def index():
    return render_template_string(LINKEDIN_HTML_TEMPLATE)

@app.route('/api/linkedin/test', methods=['POST'])
def test_linkedin_connection():
    data = request.json
    access_token = data.get('accessToken')
    
    if not access_token:
        return jsonify({"success": False, "error": "Access token is required"})
    
    client = LinkedInAPIClient(access_token)
    result = client.test_connection()
    return jsonify(result)

@app.route('/api/linkedin/lead-forms', methods=['POST'])
def get_lead_forms():
    data = request.json
    access_token = data.get('accessToken')
    owner_type = data.get('ownerType')
    owner_id = data.get('ownerId')
    
    if not all([access_token, owner_type, owner_id]):
        return jsonify({"success": False, "error": "Missing required parameters"})
    
    client = LinkedInAPIClient(access_token)
    result = client.get_lead_forms(owner_type, owner_id)
    return jsonify(result)

@app.route('/api/linkedin/lead-responses', methods=['POST'])
def get_lead_responses():
    data = request.json
    access_token = data.get('accessToken')
    form_id = data.get('formId')
    max_results = data.get('maxResults', 10)
    
    if not all([access_token, form_id]):
        return jsonify({"success": False, "error": "Missing required parameters"})
    
    client = LinkedInAPIClient(access_token)
    result = client.get_lead_responses(form_id, max_results)
    return jsonify(result)

@app.route('/api/linkedin/events', methods=['POST'])
def get_events():
    data = request.json
    access_token = data.get('accessToken')
    org_id = data.get('orgId')
    max_results = data.get('maxResults', 10)
    
    if not all([access_token, org_id]):
        return jsonify({"success": False, "error": "Missing required parameters"})
    
    client = LinkedInAPIClient(access_token)
    result = client.get_events(org_id, max_results)
    return jsonify(result)

@app.route('/health')
def health():
    return jsonify({"status": "running", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    print("🔗 Starting LinkedIn API Scraper...")
    print("📱 Open your browser and go to: http://localhost:5002")
    print("⏹️  Press Ctrl+C to stop the server")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5002)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
