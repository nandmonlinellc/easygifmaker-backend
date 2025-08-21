#!/usr/bin/env python3
"""
API Usage Dashboard - View comprehensive usage statistics
Run this script to get detailed insights about your API usage
"""

import sys
import os
import requests
from datetime import datetime, timedelta
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# You'll need to set your admin token
ADMIN_TOKEN = os.environ.get('ADMIN_TOKEN', 'your-admin-token-here')
BASE_URL = 'https://easygifmaker.com'  # Change to localhost:5001 for local testing

def make_admin_request(endpoint, hours=24):
    """Make authenticated request to admin endpoint"""
    try:
        headers = {'Authorization': f'Bearer {ADMIN_TOKEN}'}
        params = {'hours': hours} if 'hours' in endpoint or '?' not in endpoint else {}
        url = f"{BASE_URL}{endpoint}"
        
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Error {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None

def print_separator(title):
    """Print formatted section separator"""
    print("\n" + "="*60)
    print(f"🔍 {title}")
    print("="*60)

def display_ai_usage(hours=24):
    """Display AI endpoint usage statistics"""
    print_separator(f"AI USAGE REPORT (Last {hours} hours)")
    
    data = make_admin_request('/admin/ai-usage', hours)
    if not data:
        return
    
    print(f"📊 Total AI Requests: {data['total_ai_requests']}")
    print(f"⚙️  Total AI Jobs: {data['total_ai_jobs']}")
    print(f"✅ Success Rate: {data['success_rate']:.1%}")
    
    print(f"\n🎯 Usage by Endpoint:")
    for endpoint, count in data['usage_by_endpoint'].items():
        print(f"   {endpoint}: {count} requests")
    
    print(f"\n🌐 Top Users by IP:")
    for i, (ip, info) in enumerate(data['usage_by_ip'].items(), 1):
        print(f"   {i}. {ip}: {info['total']} total requests")
        for endpoint, count in info['endpoints'].items():
            print(f"      └─ {endpoint}: {count}")
        if i >= 5:  # Show top 5
            break

def display_comprehensive_stats(hours=168):
    """Display comprehensive API statistics"""
    print_separator(f"COMPREHENSIVE API STATS (Last {hours} hours)")
    
    data = make_admin_request('/admin/api-stats', hours)
    if not data:
        return
    
    print(f"📈 Total Requests: {data['total_requests']}")
    print(f"👥 Unique IPs: {data['unique_ips']}")
    
    print(f"\n📂 Usage by Category:")
    for category, info in data['by_category'].items():
        if info['count'] > 0:
            print(f"   {category.upper()}: {info['count']} requests from {info['unique_ips']} IPs")
    
    print(f"\n🔥 Top Endpoints:")
    for i, (endpoint, count) in enumerate(data['by_endpoint'].items(), 1):
        print(f"   {i}. {endpoint}: {count}")
        if i >= 10:  # Show top 10
            break
    
    print(f"\n👑 Top IPs:")
    for i, (ip, count) in enumerate(data['top_ips'].items(), 1):
        print(f"   {i}. {ip}: {count} requests")
        if i >= 5:  # Show top 5
            break

def display_user_analysis(hours=168):
    """Display user behavior analysis"""
    print_separator(f"USER BEHAVIOR ANALYSIS (Last {hours} hours)")
    
    data = make_admin_request('/admin/user-analysis', hours)
    if not data:
        return
    
    print(f"👥 Total Unique Users: {data['total_unique_users']}")
    
    print(f"\n🏆 Most Active Users:")
    for i, user in enumerate(data['users'][:10], 1):
        duration = user['session_duration_minutes']
        rpm = user['requests_per_minute']
        endpoints = len(user['endpoints_used'])
        
        print(f"   {i}. IP: {user['ip']}")
        print(f"      📊 {user['total_requests']} requests across {endpoints} endpoints")
        print(f"      ⏱️  Session: {duration:.1f} min ({rpm:.1f} req/min)")
        print(f"      🕒 {user['first_seen']} → {user['last_seen']}")
        
        # Show most used endpoints for this user
        endpoint_counts = {}
        for endpoint in user['endpoints_used']:
            if endpoint not in endpoint_counts:
                endpoint_counts[endpoint] = user['endpoints_used'].count(endpoint)
        
        top_endpoints = sorted(endpoint_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        if top_endpoints:
            print(f"      🎯 Top endpoints: {', '.join([f'{ep}({cnt})' for ep, cnt in top_endpoints])}")
        print()

def main():
    """Main dashboard function"""
    print("🌐 EasyGIFMaker API Usage Dashboard")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    if ADMIN_TOKEN == 'your-admin-token-here':
        print("\n⚠️  Please set ADMIN_TOKEN environment variable or update the script")
        print("   Export your admin token: export ADMIN_TOKEN='your-actual-token'")
        return
    
    # Display different views
    display_ai_usage(24)           # Last 24 hours for AI
    display_comprehensive_stats(168)  # Last 7 days comprehensive
    display_user_analysis(168)     # Last 7 days user behavior
    
    print_separator("SUMMARY")
    print("✅ Dashboard completed!")
    print("\n💡 Tips:")
    print("   - Run with different time ranges by modifying the hours parameters")
    print("   - Monitor AI usage patterns to understand user behavior")
    print("   - Check user analysis for potential API abuse")
    print("   - Use comprehensive stats to plan infrastructure scaling")

if __name__ == "__main__":
    main()
