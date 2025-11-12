#!/usr/bin/env python3
"""
Simple Web Scraper - Minimal PhantomBuster Alternative
This is a simplified version that focuses on core functionality
"""

import time
import json
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import requests
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# Simple HTML template
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Simple Web Scraper</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .container { max-width: 800px; margin: 0 auto; }
        .form-group { margin: 20px 0; }
        label { display: block; margin-bottom: 5px; font-weight: bold; }
        input, textarea, select { width: 100%; padding: 10px; margin-bottom: 10px; }
        button { background: #007bff; color: white; padding: 10px 20px; border: none; cursor: pointer; }
        button:hover { background: #0056b3; }
        .result { background: #f8f9fa; padding: 20px; margin: 20px 0; border-radius: 5px; }
        .error { background: #f8d7da; color: #721c24; padding: 10px; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🕷️ Simple Web Scraper</h1>
        <p>Free alternative to PhantomBuster - No monthly fees!</p>
        
        <form id="scrapeForm">
            <div class="form-group">
                <label>Website URL:</label>
                <input type="url" id="url" placeholder="https://example.com" required>
            </div>
            
            <div class="form-group">
                <label>CSS Selectors (JSON format):</label>
                <textarea id="selectors" rows="4" placeholder='{"title": "h1", "description": ".description", "links": "a"}' required>{"title": "h1", "description": ".description", "links": "a"}</textarea>
            </div>
            
            <div class="form-group">
                <label>Max Results:</label>
                <input type="number" id="maxResults" value="10" min="1" max="100">
            </div>
            
            <button type="submit">🚀 Start Scraping</button>
        </form>
        
        <div id="results"></div>
    </div>

    <script>
        document.getElementById('scrapeForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const url = document.getElementById('url').value;
            const selectors = document.getElementById('selectors').value;
            const maxResults = document.getElementById('maxResults').value;
            
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = '<div class="result">🔄 Scraping in progress...</div>';
            
            try {
                const response = await fetch('/scrape', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        url: url,
                        selectors: JSON.parse(selectors),
                        maxResults: parseInt(maxResults)
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    resultsDiv.innerHTML = `<div class="error">❌ Error: ${data.error}</div>`;
                } else {
                    resultsDiv.innerHTML = `
                        <div class="result">
                            <h3>✅ Scraping Complete!</h3>
                            <p><strong>URL:</strong> ${url}</p>
                            <p><strong>Results Found:</strong> ${Object.keys(data.results).length} data types</p>
                            <pre>${JSON.stringify(data.results, null, 2)}</pre>
                        </div>
                    `;
                }
            } catch (error) {
                resultsDiv.innerHTML = `<div class="error">❌ Error: ${error.message}</div>`;
            }
        });
    </script>
</body>
</html>
"""

class SimpleScraper:
    def __init__(self):
        self.driver = None
        
    def start_browser(self, headless=True):
        """Start Chrome browser"""
        options = Options()
        if headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=options)
            return True
        except Exception as e:
            print(f"Error starting browser: {e}")
            return False
    
    def stop_browser(self):
        """Stop browser"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def scrape_website(self, url, selectors, max_results=10):
        """Scrape website data"""
        if not self.driver:
            if not self.start_browser():
                return {"error": "Failed to start browser"}
        
        try:
            print(f"Scraping: {url}")
            self.driver.get(url)
            time.sleep(2)  # Wait for page to load
            
            results = {}
            
            for key, selector in selectors.items():
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        if len(elements) == 1:
                            results[key] = elements[0].text.strip()
                        else:
                            results[key] = [elem.text.strip() for elem in elements[:max_results]]
                    else:
                        results[key] = None
                except Exception as e:
                    results[key] = f"Error: {str(e)}"
            
            return {"success": True, "results": results}
            
        except Exception as e:
            return {"error": f"Scraping failed: {str(e)}"}
    
    def scrape_linkedin_profiles(self, search_url, max_profiles=10):
        """Simple LinkedIn profile scraper"""
        if not self.driver:
            if not self.start_browser():
                return {"error": "Failed to start browser"}
        
        try:
            print(f"Scraping LinkedIn: {search_url}")
            self.driver.get(search_url)
            time.sleep(3)
            
            profiles = []
            profile_elements = self.driver.find_elements(By.CSS_SELECTOR, '.entity-result__item')
            
            for element in profile_elements[:max_profiles]:
                try:
                    name_elem = element.find_element(By.CSS_SELECTOR, '.entity-result__title-text a')
                    title_elem = element.find_element(By.CSS_SELECTOR, '.entity-result__primary-subtitle')
                    company_elem = element.find_element(By.CSS_SELECTOR, '.entity-result__secondary-subtitle')
                    
                    profiles.append({
                        'name': name_elem.text.strip(),
                        'title': title_elem.text.strip(),
                        'company': company_elem.text.strip(),
                        'url': name_elem.get_attribute('href')
                    })
                except:
                    continue
            
            return {"success": True, "profiles": profiles}
            
        except Exception as e:
            return {"error": f"LinkedIn scraping failed: {str(e)}"}

# Global scraper instance
scraper = SimpleScraper()

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scrape', methods=['POST'])
def scrape():
    data = request.json
    url = data.get('url')
    selectors = data.get('selectors', {})
    max_results = data.get('maxResults', 10)
    
    if not url:
        return jsonify({"error": "URL is required"})
    
    try:
        result = scraper.scrape_website(url, selectors, max_results)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/linkedin', methods=['POST'])
def scrape_linkedin():
    data = request.json
    search_url = data.get('search_url')
    max_profiles = data.get('max_profiles', 10)
    
    if not search_url:
        return jsonify({"error": "Search URL is required"})
    
    try:
        result = scraper.scrape_linkedin_profiles(search_url, max_profiles)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})

@app.route('/health')
def health():
    return jsonify({"status": "running", "timestamp": datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting Simple Web Scraper...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop the server")
    
    try:
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    finally:
        scraper.stop_browser()
