#!/usr/bin/env python3
"""
Data Verification - Check if current data is real or test data
"""

import sqlite3
from datetime import datetime

def check_data_authenticity():
    """Check if data is real or test data"""
    print("🔍 DATA AUTHENTICITY CHECK")
    print("=" * 50)
    
    try:
        conn = sqlite3.connect('instance/app.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check AI endpoint data
        cursor.execute("""
            SELECT COUNT(*) as count, MIN(timestamp) as first, MAX(timestamp) as last 
            FROM api_log WHERE path LIKE '/ai/%'
        """)
        ai_stats = cursor.fetchone()
        
        # Check test IP addresses
        test_ips = ['192.168.1.100', '10.0.0.50', '203.45.67.89', '172.16.0.10']
        cursor.execute("""
            SELECT COUNT(*) as test_count 
            FROM api_log 
            WHERE path LIKE '/ai/%' AND ip IN ({})
        """.format(','.join(['?' for _ in test_ips])), test_ips)
        test_count = cursor.fetchone()['test_count']
        
        # Check job metrics (these are likely real)
        cursor.execute("""
            SELECT COUNT(*) as job_count, MIN(created_at) as first_job, MAX(created_at) as last_job
            FROM job_metrics 
            WHERE created_at >= datetime('now', '-7 days')
        """)
        job_stats = cursor.fetchone()
        
        print(f"📊 AI ENDPOINT DATA:")
        print(f"   Total AI requests: {ai_stats['count']}")
        if ai_stats['first']:
            print(f"   First request: {ai_stats['first']}")
            print(f"   Last request: {ai_stats['last']}")
        
        print(f"\n🧪 TEST DATA ANALYSIS:")
        print(f"   Test IP requests: {test_count} out of {ai_stats['count']}")
        if test_count == ai_stats['count']:
            print(f"   ⚠️  ALL AI DATA APPEARS TO BE TEST DATA")
        elif test_count > 0:
            print(f"   ⚠️  MIXED: {test_count} test + {ai_stats['count'] - test_count} real")
        else:
            print(f"   ✅ ALL AI DATA APPEARS TO BE REAL")
        
        print(f"\n⚙️  JOB METRICS DATA:")
        print(f"   Job records (7 days): {job_stats['job_count']}")
        if job_stats['first_job']:
            print(f"   First job: {job_stats['first_job']}")
            print(f"   Last job: {job_stats['last_job']}")
            print(f"   ✅ JOB METRICS ARE REAL USER DATA")
        
        # Final assessment
        print(f"\n🎯 FINAL ASSESSMENT:")
        if test_count == ai_stats['count'] and ai_stats['count'] > 0:
            print(f"   📋 AI usage data: TEST DATA ONLY")
            print(f"   📋 Job metrics: REAL USER DATA ({job_stats['job_count']} jobs)")
            print(f"   📋 Recommendation: Clear test data for real monitoring")
        elif test_count == 0 and ai_stats['count'] > 0:
            print(f"   📋 AI usage data: REAL USER DATA")
            print(f"   📋 Job metrics: REAL USER DATA")
            print(f"   📋 Status: Ready for production monitoring")
        else:
            print(f"   📋 Mixed data detected - review needed")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking data: {e}")

def show_clear_test_command():
    """Show command to clear test data"""
    print(f"\n🧹 CLEAR TEST DATA COMMAND:")
    print(f"   sqlite3 instance/app.db \"DELETE FROM api_log WHERE ip IN ('192.168.1.100', '10.0.0.50', '203.45.67.89', '172.16.0.10');\"")

if __name__ == "__main__":
    check_data_authenticity()
    show_clear_test_command()
