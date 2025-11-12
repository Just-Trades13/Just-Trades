#!/usr/bin/env python3
"""
Phantom Scraper - Free Web Scraping Tool
Quick start script for running the application
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_requirements():
    """Check if all requirements are installed"""
    try:
        import selenium
        import flask
        import pandas
        import beautifulsoup4
        print("✅ All requirements are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing requirement: {e}")
        print("Installing requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return True

def check_chrome():
    """Check if Chrome is installed"""
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium-browser"
    ]
    
    for path in chrome_paths:
        if os.path.exists(path):
            print("✅ Chrome browser found")
            return True
    
    print("❌ Chrome browser not found")
    print("Please install Google Chrome from: https://www.google.com/chrome/")
    return False

def create_directories():
    """Create necessary directories"""
    directories = ["output", "templates"]
    for directory in directories:
        Path(directory).mkdir(exist_ok=True)
    print("✅ Directories created")

def main():
    """Main function to start the application"""
    print("🚀 Starting Phantom Scraper...")
    print("=" * 50)
    
    # Check requirements
    if not check_requirements():
        print("❌ Failed to install requirements")
        return
    
    # Check Chrome
    if not check_chrome():
        print("❌ Chrome browser is required")
        return
    
    # Create directories
    create_directories()
    
    # Start the application
    print("\n🌐 Starting web server...")
    print("📱 Open your browser and go to: http://localhost:5000")
    print("⏹️  Press Ctrl+C to stop the server")
    print("=" * 50)
    
    try:
        from app import app
        app.run(debug=False, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        print("Try running: python app.py")

if __name__ == "__main__":
    main()
