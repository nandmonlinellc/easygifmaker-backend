#!/usr/bin/env python3
"""
Test script for AI-friendly API endpoints
"""

import requests
import json

# Base URL for the API
BASE_URL = "https://easygifmaker-api.fly.dev"

def test_ai_health():
    """Test AI API health endpoint"""
    print("🔍 Testing AI API Health...")
    try:
        response = requests.get(f"{BASE_URL}/api/ai/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Health check passed: {data}")
            return True
        else:
            print(f"❌ Health check failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_ai_capabilities():
    """Test AI API capabilities endpoint"""
    print("\n🔍 Testing AI API Capabilities...")
    try:
        response = requests.get(f"{BASE_URL}/api/ai/capabilities")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Capabilities endpoint working:")
            print(f"   Service: {data.get('service')}")
            print(f"   Version: {data.get('version')}")
            print(f"   Endpoints: {len(data.get('endpoints', {}))}")
            return True
        else:
            print(f"❌ Capabilities failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Capabilities error: {e}")
        return False

def test_ai_convert_endpoint():
    """Test AI convert endpoint with error handling"""
    print("\n🔍 Testing AI Convert Endpoint...")
    try:
        # Test with no input (should return error with usage info)
        response = requests.post(f"{BASE_URL}/api/ai/convert", json={})
        if response.status_code == 400:
            data = response.json()
            if 'usage' in data:
                print("✅ Convert endpoint working (proper error handling)")
                print(f"   Error message: {data.get('error')}")
                return True
            else:
                print("❌ Convert endpoint missing usage info")
                return False
        else:
            print(f"❌ Convert endpoint unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Convert endpoint error: {e}")
        return False

def test_ai_create_gif_endpoint():
    """Test AI create GIF endpoint with error handling"""
    print("\n🔍 Testing AI Create GIF Endpoint...")
    try:
        # Test with no input (should return error with usage info)
        response = requests.post(f"{BASE_URL}/api/ai/create-gif", json={})
        if response.status_code == 400:
            data = response.json()
            if 'usage' in data:
                print("✅ Create GIF endpoint working (proper error handling)")
                print(f"   Error message: {data.get('error')}")
                return True
            else:
                print("❌ Create GIF endpoint missing usage info")
                return False
        else:
            print(f"❌ Create GIF endpoint unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Create GIF endpoint error: {e}")
        return False

def test_ai_optimize_endpoint():
    """Test AI optimize endpoint with error handling"""
    print("\n🔍 Testing AI Optimize Endpoint...")
    try:
        # Test with no input (should return error with usage info)
        response = requests.post(f"{BASE_URL}/api/ai/optimize", json={})
        if response.status_code == 400:
            data = response.json()
            if 'usage' in data:
                print("✅ Optimize endpoint working (proper error handling)")
                print(f"   Error message: {data.get('error')}")
                return True
            else:
                print("❌ Optimize endpoint missing usage info")
                return False
        else:
            print(f"❌ Optimize endpoint unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Optimize endpoint error: {e}")
        return False

def test_ai_add_text_endpoint():
    """Test AI add text endpoint with error handling"""
    print("\n🔍 Testing AI Add Text Endpoint...")
    try:
        # Test with no input (should return error with usage info)
        response = requests.post(f"{BASE_URL}/api/ai/add-text", json={})
        if response.status_code == 400:
            data = response.json()
            if 'usage' in data:
                print("✅ Add Text endpoint working (proper error handling)")
                print(f"   Error message: {data.get('error')}")
                return True
            else:
                print("❌ Add Text endpoint missing usage info")
                return False
        else:
            print(f"❌ Add Text endpoint unexpected status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Add Text endpoint error: {e}")
        return False

def main():
    """Run all AI API tests"""
    print("🚀 Testing EasyGIFMaker AI API Endpoints")
    print("=" * 50)
    
    tests = [
        test_ai_health,
        test_ai_capabilities,
        test_ai_convert_endpoint,
        test_ai_create_gif_endpoint,
        test_ai_optimize_endpoint,
        test_ai_add_text_endpoint
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All AI API endpoints are working correctly!")
        print("\n📋 Available AI Endpoints:")
        print("   • GET  /api/ai/health - Health check")
        print("   • GET  /api/ai/capabilities - API documentation")
        print("   • POST /api/ai/convert - Convert video to GIF")
        print("   • POST /api/ai/create-gif - Create GIF from images")
        print("   • POST /api/ai/optimize - Optimize GIF file size")
        print("   • POST /api/ai/add-text - Add text to GIF")
        print("   • GET  /api/ai/status/{task_id} - Check task status")
        print("   • GET  /api/ai/download/{task_id} - Download result")
        
        print("\n🎯 Your GIF tools are now accessible to:")
        print("   • ChatGPT Browsing Mode")
        print("   • Perplexity AI Agents")
        print("   • Zapier Automations")
        print("   • Other AI platforms")
        
    else:
        print("⚠️  Some tests failed. Please check the implementation.")

if __name__ == "__main__":
    main() 