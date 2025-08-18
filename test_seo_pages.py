#!/usr/bin/env python3
"""
Test script to verify SEO pages are working correctly.
"""

import requests
import time

def test_seo_pages():
    base_url = "http://localhost:5001"
    
    # Test pages to check
    test_pages = [
        "/convert/mp4-to-gif",
        "/convert/youtube-to-gif", 
        "/features/reverse-gif",
        "/optimize/gif-under-5mb",
        "/tools/add-text-to-gif"
    ]
    
    print("=== Testing SEO Pages ===\n")
    
    for page in test_pages:
        try:
            response = requests.get(f"{base_url}{page}", timeout=5)
            if response.status_code == 200:
                print(f"✅ {page} - Status: {response.status_code}")
                
                # Check for important SEO elements
                content = response.text
                if "mp4 to gif" in content.lower() or "youtube to gif" in content.lower() or "reverse gif" in content.lower():
                    print(f"   📄 Content found")
                if "schema.org" in content:
                    print(f"   🏷️  Schema markup found")
                if "og:title" in content:
                    print(f"   📱 Open Graph tags found")
            else:
                print(f"❌ {page} - Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {page} - Error: {e}")
    
    print("\n=== Testing Sitemap ===")
    try:
        response = requests.get(f"{base_url}/sitemap.xml", timeout=5)
        if response.status_code == 200:
            print("✅ Sitemap accessible")
            if "mp4-to-gif" in response.text:
                print("   📄 SEO pages found in sitemap")
        else:
            print(f"❌ Sitemap - Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Sitemap - Error: {e}")
    
    print("\n=== Testing Robots.txt ===")
    try:
        response = requests.get(f"{base_url}/robots.txt", timeout=5)
        if response.status_code == 200:
            print("✅ Robots.txt accessible")
            if "sitemap" in response.text:
                print("   📄 Sitemap reference found")
        else:
            print(f"❌ Robots.txt - Status: {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Robots.txt - Error: {e}")

if __name__ == "__main__":
    print("Make sure the Flask server is running on port 5001")
    print("You can start it with: python -m src.main")
    print()
    test_seo_pages() 