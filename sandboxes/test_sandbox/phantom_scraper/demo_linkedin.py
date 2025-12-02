#!/usr/bin/env python3
"""
LinkedIn API Demo - Shows what the interface looks like without real credentials
"""

from flask import Flask, render_template_string, request, jsonify
import json
import time

app = Flask(__name__)

# Demo HTML Template
DEMO_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>LinkedIn API Demo</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .demo-section { background: #e3f2fd; padding: 20px; border-radius: 5px; margin: 20px 0; }
        .success { background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 10px 0; }
        .warning { background: #fff3cd; color: #856404; padding: 15px; border-radius: 5px; margin: 10px 0; }
        pre { background: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }
        button { background: #0077b5; color: white; padding: 12px 25px; border: none; cursor: pointer; border-radius: 5px; margin: 10px 5px; }
        button:hover { background: #005885; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔗 LinkedIn API Demo</h1>
        <p>This shows what your LinkedIn API scraper will look like once you get credentials!</p>
        
        <div class="demo-section">
            <h3>📋 What You'll Need:</h3>
            <ul>
                <li>LinkedIn Developer App (free to create)</li>
                <li>API permissions: <code>r_marketing_leadgen_automation</code>, <code>rw_ads</code>, <code>r_ads</code></li>
                <li>Access token from OAuth 2.0 flow</li>
                <li>Organization or Sponsored Account ID</li>
            </ul>
        </div>

        <div class="demo-section">
            <h3>🎯 Demo: What You Can Extract</h3>
            <p>Click the buttons below to see sample data you'll be able to extract:</p>
            
            <button onclick="showLeadForms()">📋 Lead Forms</button>
            <button onclick="showLeadResponses()">📊 Lead Responses</button>
            <button onclick="showEvents()">🎯 Events</button>
            <button onclick="showProfiles()">👥 Profile Data</button>
        </div>

        <div id="demoResults"></div>

        <div class="demo-section">
            <h3>🚀 Next Steps:</h3>
            <ol>
                <li>Go to <a href="https://www.linkedin.com/developers/" target="_blank">LinkedIn Developer Portal</a></li>
                <li>Create a new app</li>
                <li>Request Marketing Developer Platform access</li>
                <li>Get your access token</li>
                <li>Use the real LinkedIn API scraper!</li>
            </ol>
        </div>
    </div>

    <script>
        function showLeadForms() {
            const sampleData = {
                "forms": [
                    {
                        "id": "urn:li:leadGenForm:123456",
                        "name": "Software Engineer Interest Form",
                        "state": "PUBLISHED",
                        "creationLocale": "en_US",
                        "content": {
                            "name": "Tech Talent Lead Form",
                            "questions": [
                                {
                                    "question": "What's your experience level?",
                                    "type": "SINGLE_CHOICE",
                                    "options": ["Entry Level", "Mid Level", "Senior Level"]
                                },
                                {
                                    "question": "What programming languages do you know?",
                                    "type": "MULTIPLE_CHOICE",
                                    "options": ["Python", "JavaScript", "Java", "C++"]
                                }
                            ]
                        }
                    },
                    {
                        "id": "urn:li:leadGenForm:789012",
                        "name": "Marketing Newsletter Signup",
                        "state": "PUBLISHED",
                        "creationLocale": "en_US",
                        "content": {
                            "name": "Marketing Lead Form",
                            "questions": [
                                {
                                    "question": "Company size",
                                    "type": "SINGLE_CHOICE",
                                    "options": ["1-10", "11-50", "51-200", "200+"]
                                }
                            ]
                        }
                    }
                ]
            };
            
            document.getElementById('demoResults').innerHTML = `
                <div class="success">✅ Found ${sampleData.forms.length} lead forms</div>
                <pre>${JSON.stringify(sampleData, null, 2)}</pre>
            `;
        }

        function showLeadResponses() {
            const sampleData = {
                "responses": [
                    {
                        "id": "urn:li:leadGenFormResponse:abc123",
                        "submittedAt": "2024-01-15T10:30:00Z",
                        "leadType": "SPONSORED",
                        "formResponse": {
                            "firstName": "John",
                            "lastName": "Doe",
                            "email": "john.doe@example.com",
                            "phone": "+1-555-0123",
                            "company": "Tech Corp",
                            "experience": "Senior Level",
                            "languages": ["Python", "JavaScript"]
                        }
                    },
                    {
                        "id": "urn:li:leadGenFormResponse:def456",
                        "submittedAt": "2024-01-15T11:45:00Z",
                        "leadType": "SPONSORED",
                        "formResponse": {
                            "firstName": "Jane",
                            "lastName": "Smith",
                            "email": "jane.smith@company.com",
                            "phone": "+1-555-0456",
                            "company": "Startup Inc",
                            "experience": "Mid Level",
                            "languages": ["Java", "C++"]
                        }
                    }
                ]
            };
            
            document.getElementById('demoResults').innerHTML = `
                <div class="success">✅ Found ${sampleData.responses.length} lead responses</div>
                <pre>${JSON.stringify(sampleData, null, 2)}</pre>
            `;
        }

        function showEvents() {
            const sampleData = {
                "events": [
                    {
                        "id": "urn:li:event:123456",
                        "name": "Tech Conference 2024",
                        "start": "2024-03-15T09:00:00Z",
                        "status": "ACTIVE",
                        "organizer": "urn:li:organization:789012",
                        "attendeeCount": 150,
                        "description": "Annual technology conference featuring AI and machine learning talks"
                    },
                    {
                        "id": "urn:li:event:789012",
                        "name": "Marketing Workshop",
                        "start": "2024-02-20T14:00:00Z",
                        "status": "ACTIVE",
                        "organizer": "urn:li:organization:789012",
                        "attendeeCount": 75,
                        "description": "Digital marketing strategies and LinkedIn advertising best practices"
                    }
                ]
            };
            
            document.getElementById('demoResults').innerHTML = `
                <div class="success">✅ Found ${sampleData.events.length} events</div>
                <pre>${JSON.stringify(sampleData, null, 2)}</pre>
            `;
        }

        function showProfiles() {
            const sampleData = {
                "profiles": [
                    {
                        "id": "urn:li:person:123456",
                        "firstName": "John",
                        "lastName": "Doe",
                        "headline": "Senior Software Engineer at Tech Corp",
                        "location": "San Francisco, CA",
                        "industry": "Information Technology",
                        "connections": 500,
                        "summary": "Experienced software engineer with 5+ years in Python and JavaScript development."
                    },
                    {
                        "id": "urn:li:person:789012",
                        "firstName": "Jane",
                        "lastName": "Smith",
                        "headline": "Marketing Manager at Startup Inc",
                        "location": "New York, NY",
                        "industry": "Marketing and Advertising",
                        "connections": 750,
                        "summary": "Digital marketing specialist focused on growth hacking and social media strategy."
                    }
                ]
            };
            
            document.getElementById('demoResults').innerHTML = `
                <div class="success">✅ Found ${sampleData.profiles.length} profiles</div>
                <pre>${JSON.stringify(sampleData, null, 2)}</pre>
            `;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(DEMO_HTML)

if __name__ == '__main__':
    print("🎯 Starting LinkedIn API Demo...")
    print("📱 Open your browser and go to: http://localhost:5003")
    print("⏹️  Press Ctrl+C to stop the server")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5003)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
