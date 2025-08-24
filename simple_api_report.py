#!/usr/bin/env python3
"""
🚀 EasyGIFMaker AI API Usage Report
Simple and reliable analytics for your AI API endpoints
"""

import sqlite3
from datetime import datetime
import os

def get_database_path():
    """Get the database path"""
    db_path = "instance/app.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return None
    return db_path

def main():
    """Main analytics function"""
    db_path = get_database_path()
    if not db_path:
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("🤖 EasyGIFMaker AI API Usage Report")
    print("=" * 50)
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Total Stats
    cursor.execute("""
        SELECT COUNT(*) as total_requests,
               COUNT(DISTINCT ip) as unique_users
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
    """)
    
    total_requests, unique_users = cursor.fetchone()
    print(f"📊 SUMMARY")
    print(f"   Total API Requests: {total_requests:,}")
    print(f"   Unique Users: {unique_users}")
    print()
    
    # Endpoint Usage
    cursor.execute("""
        SELECT path, COUNT(*) as requests, COUNT(DISTINCT ip) as users
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
        GROUP BY path
        ORDER BY requests DESC
    """)
    
    endpoints = cursor.fetchall()
    print("🎯 ENDPOINT USAGE")
    print("-" * 30)
    for path, requests, users in endpoints:
        percentage = (requests / total_requests * 100) if total_requests > 0 else 0
        print(f"📍 {path}")
        print(f"   ├─ {requests:,} requests ({percentage:.1f}%)")
        print(f"   └─ {users} unique users")
        print()
    
    # Top Users
    cursor.execute("""
        SELECT ip, COUNT(*) as requests, 
               MIN(timestamp) as first_seen,
               MAX(timestamp) as last_seen
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
        GROUP BY ip
        ORDER BY requests DESC
        LIMIT 5
    """)
    
    users = cursor.fetchall()
    print("👥 TOP USERS")
    print("-" * 30)
    for i, (ip, requests, first, last) in enumerate(users, 1):
        print(f"#{i} {ip}")
        print(f"   ├─ {requests} requests")
        print(f"   ├─ First: {first[:10]}")
        print(f"   └─ Last: {last[:10]}")
        print()
    
    # Recent Activity
    cursor.execute("""
        SELECT timestamp, ip, path
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    
    recent = cursor.fetchall()
    print("🕐 RECENT ACTIVITY (Last 5)")
    print("-" * 30)
    for timestamp, ip, path in recent:
        # Simple time formatting
        dt_str = timestamp[:16]  # Just YYYY-MM-DD HH:MM
        print(f"• {dt_str} | {ip} | {path}")
    
    print()
    print("🚀 Your AI API is getting good usage!")
    print("💡 Most popular endpoint:", endpoints[0][0] if endpoints else "None")
    
    conn.close()

if __name__ == "__main__":
    main()
