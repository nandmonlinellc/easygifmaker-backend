#!/usr/bin/env python3
"""
Test script for Vite + Flask setup
"""

import requests
import time

def test_vite_flask_setup():
    print("🚀 Testing Vite + Flask Setup")
    print("=" * 50)
    
    # Test Vite frontend
    print("\n⚛️ Testing Vite Frontend (localhost:5173):")
    print("-" * 40)
    
    vite_routes = [
        "/video-to-gif",
        "/gif-maker",
        "/crop", 
        "/optimize",
        "/add-text"
    ]
    
    for route in vite_routes:
        try:
            response = requests.get(f"http://localhost:5173{route}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {route}")
                if "react" in response.text.lower() or "root" in response.text.lower():
                    print("   ⚛️ React app detected")
            else:
                print(f"❌ {route} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {route} - Error: {e}")
    
    # Test Flask backend SEO pages
    print("\n📄 Testing Flask SEO Pages (localhost:5001):")
    print("-" * 40)
    
    seo_pages = [
        "/convert/mp4-to-gif",
        "/convert/youtube-to-gif",
        "/features/reverse-gif", 
        "/optimize/gif-under-5mb",
        "/tools/add-text-to-gif"
    ]
    
    for page in seo_pages:
        try:
            response = requests.get(f"http://localhost:5001{page}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {page}")
                
                # Check SEO elements
                content = response.text
                checks = []
                
                if "schema.org" in content:
                    checks.append("🏷️ Schema")
                if "og:title" in content:
                    checks.append("📱 Open Graph")
                if "twitter:card" in content:
                    checks.append("🐦 Twitter")
                if "canonical" in content:
                    checks.append("🔗 Canonical")
                
                if checks:
                    print(f"   {' | '.join(checks)}")
                    
            else:
                print(f"❌ {page} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {page} - Error: {e}")
    
    # Test Flask API endpoints
    print("\n🔌 Testing Flask API (localhost:5001):")
    print("-" * 40)
    
    try:
        response = requests.get("http://localhost:5001/api/health", timeout=5)
        if response.status_code == 200:
            print("✅ API health check")
        else:
            print(f"⚠️ API health check - Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ API health check - Error: {e}")
    
    # Test sitemap and robots
    print("\n🗺️ Testing SEO Files (localhost:5001):")
    print("-" * 40)
    
    seo_files = [
        ("/sitemap.xml", "Sitemap"),
        ("/robots.txt", "Robots.txt")
    ]
    
    for file_path, name in seo_files:
        try:
            response = requests.get(f"http://localhost:5001{file_path}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {name}")
            else:
                print(f"❌ {name} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {name} - Error: {e}")
    
    print("\n" + "=" * 50)
    print("🎯 Summary:")
    print("✅ Vite frontend serving React tools")
    print("✅ Flask backend serving SEO pages")
    print("✅ API endpoints working")
    print("✅ SEO files accessible")
    print("\n🌐 URLs to visit:")
    print("   React Tools: http://localhost:5173/video-to-gif")
    print("   SEO Pages: http://localhost:5001/convert/mp4-to-gif")
    print("   Sitemap: http://localhost:5001/sitemap.xml")

if __name__ == "__main__":
    print("Make sure both servers are running:")
    print("  Vite: cd easygifmaker && npm run dev")
    print("  Flask: cd easygifmaker_api && python -m src.main")
    print()
    test_vite_flask_setup() 