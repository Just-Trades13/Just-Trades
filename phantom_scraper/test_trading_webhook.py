#!/usr/bin/env python3
"""
Test script for TradingView to Tradovate webhook system
"""

import requests
import json
import time
from datetime import datetime

def test_webhook_connection():
    """Test basic webhook connectivity"""
    print("🔍 Testing webhook connection...")
    
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code == 200:
            print("✅ Webhook server is running")
            print(f"Response: {response.json()}")
            return True
        else:
            print(f"❌ Webhook server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to webhook server. Is it running?")
        print("Start it with: python trading_webhook_server.py")
        return False
    except Exception as e:
        print(f"❌ Error testing webhook: {e}")
        return False

def test_buy_alert():
    """Test a buy alert"""
    print("\n📈 Testing BUY alert...")
    
    alert_data = {
        "symbol": "ES1!",
        "action": "buy",
        "quantity": 1,
        "price": 4500.0,
        "strategy": "test_strategy",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            "http://localhost:8080/webhook",
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Buy alert processed successfully")
        else:
            print("❌ Buy alert failed")
            
    except Exception as e:
        print(f"❌ Error sending buy alert: {e}")

def test_sell_alert():
    """Test a sell alert"""
    print("\n📉 Testing SELL alert...")
    
    alert_data = {
        "symbol": "NQ1!",
        "action": "sell",
        "quantity": 2,
        "price": 15000.0,
        "stop_loss": 15100.0,
        "take_profit": 14900.0,
        "strategy": "test_strategy",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            "http://localhost:8080/webhook",
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Sell alert processed successfully")
        else:
            print("❌ Sell alert failed")
            
    except Exception as e:
        print(f"❌ Error sending sell alert: {e}")

def test_close_alert():
    """Test a close position alert"""
    print("\n🔄 Testing CLOSE alert...")
    
    alert_data = {
        "symbol": "ES1!",
        "action": "close",
        "strategy": "test_strategy",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        response = requests.post(
            "http://localhost:8080/webhook",
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Close alert processed successfully")
        else:
            print("❌ Close alert failed")
            
    except Exception as e:
        print(f"❌ Error sending close alert: {e}")

def test_invalid_alert():
    """Test an invalid alert format"""
    print("\n❌ Testing INVALID alert...")
    
    alert_data = {
        "invalid": "data",
        "missing": "required_fields"
    }
    
    try:
        response = requests.post(
            "http://localhost:8080/webhook",
            json=alert_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 400:
            print("✅ Invalid alert properly rejected")
        else:
            print("❌ Invalid alert should have been rejected")
            
    except Exception as e:
        print(f"❌ Error testing invalid alert: {e}")

def test_account_info():
    """Test account information endpoint"""
    print("\n💰 Testing account info...")
    
    try:
        response = requests.get("http://localhost:8080/account", timeout=10)
        
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2)}")
        
        if response.status_code == 200:
            print("✅ Account info retrieved successfully")
        else:
            print("❌ Account info failed")
            
    except Exception as e:
        print(f"❌ Error getting account info: {e}")

def main():
    """Run all tests"""
    print("🚀 Starting TradingView Webhook Tests")
    print("=" * 50)
    
    # Test webhook connection
    if not test_webhook_connection():
        print("\n❌ Cannot proceed - webhook server not running")
        print("Please start the webhook server first:")
        print("python trading_webhook_server.py")
        return
    
    # Run all tests
    test_buy_alert()
    time.sleep(2)
    
    test_sell_alert()
    time.sleep(2)
    
    test_close_alert()
    time.sleep(2)
    
    test_invalid_alert()
    time.sleep(2)
    
    test_account_info()
    
    print("\n" + "=" * 50)
    print("🏁 Testing completed!")
    print("\nNote: These tests will attempt to place real trades if your")
    print("Tradovate credentials are configured. Use paper trading first!")

if __name__ == "__main__":
    main()
