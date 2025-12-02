#!/usr/bin/env python3
"""
Startup script for TradingView to Tradovate automated trading system
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_requirements():
    """Check if all requirements are installed"""
    print("🔍 Checking requirements...")
    
    try:
        import flask
        import selenium
        import requests
        import undetected_chromedriver
        print("✅ All required packages are installed")
        return True
    except ImportError as e:
        print(f"❌ Missing package: {e}")
        print("Please run: pip install -r requirements.txt")
        return False

def check_config():
    """Check if configuration file exists"""
    print("🔍 Checking configuration...")
    
    env_file = Path(".env")
    if not env_file.exists():
        print("❌ .env file not found")
        print("Please copy trading_config.env to .env and configure your credentials:")
        print("cp trading_config.env .env")
        print("nano .env")
        return False
    
    # Check if credentials are configured
    with open(env_file, 'r') as f:
        content = f.read()
        if 'your_tradovate_email@example.com' in content:
            print("❌ Please configure your actual Tradovate credentials in .env file")
            return False
    
    print("✅ Configuration file found and appears to be configured")
    return True

def check_chrome():
    """Check if Chrome browser is available"""
    print("🔍 Checking Chrome browser...")
    
    try:
        # Try to find Chrome executable
        chrome_paths = [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/usr/bin/google-chrome",
            "/usr/bin/chromium-browser",
            "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe"
        ]
        
        chrome_found = False
        for path in chrome_paths:
            if os.path.exists(path):
                chrome_found = True
                break
        
        if chrome_found:
            print("✅ Chrome browser found")
            return True
        else:
            print("❌ Chrome browser not found")
            print("Please install Google Chrome browser")
            return False
            
    except Exception as e:
        print(f"❌ Error checking Chrome: {e}")
        return False

def start_webhook_server():
    """Start the webhook server"""
    print("🚀 Starting webhook server...")
    
    try:
        # Start the webhook server
        subprocess.run([sys.executable, "trading_webhook_server.py"], check=True)
    except KeyboardInterrupt:
        print("\n🛑 Webhook server stopped by user")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting webhook server: {e}")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")

def main():
    """Main startup function"""
    print("🤖 TradingView to Tradovate Automated Trading Bot")
    print("=" * 60)
    
    # Check all requirements
    if not check_requirements():
        sys.exit(1)
    
    if not check_config():
        sys.exit(1)
    
    if not check_chrome():
        sys.exit(1)
    
    print("\n✅ All checks passed!")
    print("\n📡 Webhook server will start on http://localhost:5000")
    print("📊 Configure your TradingView alerts to send to: http://localhost:5000/webhook")
    print("🛑 Press Ctrl+C to stop the server")
    print("\n" + "=" * 60)
    
    # Start the webhook server
    start_webhook_server()

if __name__ == "__main__":
    main()
