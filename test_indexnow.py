#!/usr/bin/env python3
"""Test IndexNow implementation"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.utils.indexnow import get_indexnow_client, notify_url_change, notify_urls_change

def test_indexnow():
    """Test IndexNow functionality"""
    print("🚀 Testing IndexNow Implementation")
    print("=" * 50)
    
    # Test 1: Client initialization
    try:
        client = get_indexnow_client()
        print("✅ IndexNow client initialized successfully")
        print(f"   API Key: {client.api_key[:8]}...")
        print(f"   Site URL: {client.site_url}")
        print(f"   Endpoints: {len(client.endpoints)} search engines")
    except Exception as e:
        print(f"❌ Client initialization failed: {e}")
        return False
    
    # Test 2: Single URL submission
    print("\n📤 Testing single URL submission...")
    test_url = "https://easygifmaker.com/video-to-gif"
    
    try:
        success = notify_url_change(test_url)
        if success:
            print(f"✅ Successfully submitted URL: {test_url}")
        else:
            print(f"⚠️  Partial success or failed: {test_url}")
    except Exception as e:
        print(f"❌ Single URL submission failed: {e}")
    
    # Test 3: Multiple URLs submission
    print("\n📤 Testing multiple URLs submission...")
    test_urls = [
        "https://easygifmaker.com/",
        "https://easygifmaker.com/video-to-gif",
        "https://easygifmaker.com/gif-maker",
        "https://easygifmaker.com/convert/mp4-to-gif"
    ]
    
    try:
        success = notify_urls_change(test_urls)
        if success:
            print(f"✅ Successfully submitted {len(test_urls)} URLs")
        else:
            print(f"⚠️  Partial success or failed for bulk submission")
    except Exception as e:
        print(f"❌ Multiple URLs submission failed: {e}")
    
    # Test 4: API Key file accessibility
    print(f"\n🔑 Testing API Key file accessibility...")
    key_url = f"{client.site_url}/{client.api_key}.txt"
    print(f"   Key Location: {key_url}")
    
    try:
        import requests
        response = requests.get(key_url, timeout=10)
        if response.status_code == 200 and client.api_key in response.text:
            print("✅ API Key file is accessible and contains correct key")
        else:
            print(f"⚠️  API Key file issue - Status: {response.status_code}")
    except Exception as e:
        print(f"❌ API Key file test failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 IndexNow test completed!")
    return True

if __name__ == "__main__":
    test_indexnow()
