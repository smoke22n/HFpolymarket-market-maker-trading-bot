"""
Test script for the Control Tower API Server
Verifies that all endpoints work correctly
"""
import asyncio
import json
from decimal import Decimal
import sys
import os

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import requests
import time
from datetime import datetime

# Test constants
BASE_URL = "http://localhost:8000"


def test_api_endpoints():
    """Test all API endpoints"""
    print("Testing Control Tower API endpoints...")
    
    # Test root endpoint
    print("\n1. Testing root endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/")
        if response.status_code == 200:
            print(f"✓ Root endpoint OK: {response.json()}")
        else:
            print(f"✗ Root endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"✗ Root endpoint error: {e}")
    
    # Test stats endpoint
    print("\n2. Testing /stats endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/stats")
        if response.status_code == 200:
            stats = response.json()
            print(f"✓ Stats endpoint OK: {stats}")
        else:
            print(f"✗ Stats endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Stats endpoint error: {e}")
    
    # Test history endpoint
    print("\n3. Testing /history endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/history?page=1&page_size=10")
        if response.status_code == 200:
            history = response.json()
            print(f"✓ History endpoint OK: Found {history['total_count']} total trades")
        else:
            print(f"✗ History endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ History endpoint error: {e}")
    
    # Test control endpoints
    print("\n4. Testing /control endpoints...")
    actions = ["pause", "resume"]
    
    for action in actions:
        try:
            response = requests.post(f"{BASE_URL}/control", 
                                   json={"action": action},
                                   headers={"Content-Type": "application/json"})
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Control {action} OK: {result['message']}")
            else:
                print(f"✗ Control {action} failed: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"✗ Control {action} error: {e}")
    
    # Test panic sell
    try:
        response = requests.post(f"{BASE_URL}/control", 
                               json={"action": "panic_sell"},
                               headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            result = response.json()
            print(f"✓ Control panic_sell OK: {result['message']}")
        else:
            print(f"✗ Control panic_sell failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"✗ Control panic_sell error: {e}")
    
    # Test config endpoint
    print("\n5. Testing /config endpoint...")
    config_updates = [
        {"param_name": "target_spread", "param_value": "0.0025"},
        {"param_name": "max_exposure", "param_value": "1500"},
        {"param_name": "min_order_size", "param_value": "15"}
    ]
    
    for config in config_updates:
        try:
            response = requests.post(f"{BASE_URL}/config", 
                                   json=config,
                                   headers={"Content-Type": "application/json"})
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Config update OK: {result['message']}")
            else:
                print(f"✗ Config update failed: {response.status_code}")
                print(f"Response: {response.text}")
        except Exception as e:
            print(f"✗ Config update error: {e}")


def run_api_server():
    """Function to run the API server in a separate thread for testing"""
    import threading
    from polymarket_mm_bot.control_tower.api_server import app
    import uvicorn
    
    def start_server():
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
    
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Give the server time to start
    time.sleep(3)
    
    return server_thread


if __name__ == "__main__":
    print("Starting Control Tower API test...")
    
    # Start the API server in a separate thread
    print("Starting API server...")
    server_thread = run_api_server()
    
    # Wait a bit for the server to start
    time.sleep(5)
    
    # Run the tests
    test_api_endpoints()
    
    print("\nTest completed!")