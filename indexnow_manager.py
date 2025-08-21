#!/usr/bin/env python3
"""IndexNow Management Script"""

import sys
import os
import requests
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def submit_urls_to_indexnow():
    """Submit all website URLs to IndexNow"""
    from src.utils.indexnow import notify_urls_change
    from src.seo_pages import seo_pages
    
    print("🚀 Submitting URLs to IndexNow...")
    
    # Main site URLs
    base_url = "https://easygifmaker.com"
    urls = [
        base_url,
        f"{base_url}/video-to-gif",
        f"{base_url}/gif-maker", 
        f"{base_url}/resize",
        f"{base_url}/crop",
        f"{base_url}/optimize",
        f"{base_url}/add-text",
        f"{base_url}/reverse",
        f"{base_url}/about",
        f"{base_url}/help",
        f"{base_url}/contact",
        f"{base_url}/privacy-policy",
        f"{base_url}/terms",
        f"{base_url}/cookie-policy",
        f"{base_url}/blog"
    ]
    
    # Add SEO page URLs
    seo_urls = [f"{base_url}/{p['category']}/{p['slug']}" for p in seo_pages]
    urls.extend(seo_urls)
    
    # Remove duplicates
    urls = list(set(urls))
    
    print(f"📤 Submitting {len(urls)} URLs to search engines...")
    
    success = notify_urls_change(urls)
    
    if success:
        print("✅ Successfully submitted URLs to IndexNow!")
        print(f"   Total URLs: {len(urls)}")
        print("   Search Engines: Bing, Yandex, Seznam, IndexNow API")
    else:
        print("⚠️  Partial success or submission failed")
    
    return success

def verify_api_key():
    """Verify IndexNow API key is accessible"""
    print("🔑 Verifying IndexNow API key accessibility...")
    
    api_key = "7820a1cd5e434c278e39cfeb9ec3b008"
    key_url = f"https://easygifmaker.com/{api_key}.txt"
    
    try:
        response = requests.get(key_url, timeout=10)
        if response.status_code == 200 and api_key in response.text:
            print(f"✅ API Key is accessible at: {key_url}")
            return True
        else:
            print(f"❌ API Key file issue - Status: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ API Key verification failed: {e}")
        return False

def main():
    """Main IndexNow management function"""
    print("🌐 IndexNow Management for EasyGIFMaker")
    print("=" * 50)
    
    # Verify API key first
    if not verify_api_key():
        print("⚠️  Please fix API key accessibility before continuing")
        return
    
    # Submit URLs
    success = submit_urls_to_indexnow()
    
    print("\n" + "=" * 50)
    if success:
        print("🎯 IndexNow submission completed successfully!")
        print("\n💡 Tips:")
        print("   - Run this script when you add new content")
        print("   - IndexNow helps search engines find your content faster")
        print("   - No need to run more than once per day for the same URLs")
    else:
        print("⚠️  IndexNow submission had issues - check logs for details")

if __name__ == "__main__":
    main()
