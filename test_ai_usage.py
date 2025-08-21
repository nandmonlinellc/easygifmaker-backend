#!/usr/bin/env python3
"""
Test AI Usage Tracking - Simulate AI endpoint usage for testing analytics
"""

import sqlite3
from datetime import datetime, timedelta
import random

def insert_test_data():
    """Insert test AI usage data"""
    try:
        conn = sqlite3.connect('instance/app.db')
        cursor = conn.cursor()
        
        # Create test data
        test_ips = ['192.168.1.100', '10.0.0.50', '203.45.67.89', '172.16.0.10']
        ai_endpoints = ['/ai/convert', '/ai/add-text']
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'PostmanRuntime/7.29.0',
            'python-requests/2.28.1'
        ]
        
        print("🧪 Inserting test AI usage data...")
        
        # Insert test records for the last 24 hours
        for i in range(25):  # 25 test requests
            # Random timestamp in last 24 hours
            hours_ago = random.uniform(0, 24)
            timestamp = datetime.now() - timedelta(hours=hours_ago)
            
            # Random test data
            ip = random.choice(test_ips)
            endpoint = random.choice(ai_endpoints)
            user_agent = random.choice(user_agents)
            
            cursor.execute("""
                INSERT INTO api_log (timestamp, ip, path, method, user_agent)
                VALUES (?, ?, ?, 'POST', ?)
            """, (timestamp.strftime('%Y-%m-%d %H:%M:%S'), ip, endpoint, user_agent))
        
        conn.commit()
        conn.close()
        
        print("✅ Test data inserted successfully!")
        print("💡 Now run: python3 local_usage_check.py")
        
    except Exception as e:
        print(f"❌ Error inserting test data: {e}")

if __name__ == "__main__":
    insert_test_data()
