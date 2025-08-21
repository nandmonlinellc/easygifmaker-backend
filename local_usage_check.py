#!/usr/bin/env python3
"""
Local Usage Checker - Query database directly for AI/API usage
Run this locally to check usage without web server
"""

import sys
import os
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_db_path():
    """Get database path"""
    # Try different possible locations
    possible_paths = [
        'instance/app.db',
        'src/instance/app.db',
        'app.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    print("❌ Database not found. Possible locations:")
    for path in possible_paths:
        print(f"   {path}")
    return None

def query_database(query, params=None):
    """Execute database query"""
    db_path = get_db_path()
    if not db_path:
        return None
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()
        
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"❌ Database query failed: {e}")
        return None

def analyze_ai_usage(hours=24):
    """Analyze AI endpoint usage"""
    print(f"\n🤖 AI USAGE ANALYSIS (Last {hours} hours)")
    print("=" * 50)
    
    since = datetime.now() - timedelta(hours=hours)
    since_str = since.strftime('%Y-%m-%d %H:%M:%S')
    
    # Get AI endpoint logs
    ai_query = """
        SELECT timestamp, ip, path, method, user_agent 
        FROM api_log 
        WHERE timestamp >= ? 
        AND (path LIKE '/ai/%' OR path LIKE '%ai%')
        ORDER BY timestamp DESC
    """
    
    results = query_database(ai_query, (since_str,))
    if not results:
        print("📊 No AI usage data found")
        return
    
    print(f"📊 Total AI requests: {len(results)}")
    
    # Analyze by endpoint
    endpoint_counts = Counter(row['path'] for row in results)
    print(f"\n🎯 Requests by AI Endpoint:")
    for endpoint, count in endpoint_counts.most_common():
        print(f"   {endpoint}: {count}")
    
    # Analyze by IP
    ip_counts = Counter(row['ip'] for row in results)
    print(f"\n🌐 Top IPs using AI endpoints:")
    for ip, count in ip_counts.most_common(10):
        print(f"   {ip}: {count} requests")
    
    # Analyze user agents
    ua_counts = Counter(row['user_agent'] for row in results if row['user_agent'])
    print(f"\n🔧 Top User Agents:")
    for ua, count in ua_counts.most_common(5):
        ua_short = ua[:80] + "..." if len(ua) > 80 else ua
        print(f"   {count}x: {ua_short}")

def analyze_job_metrics(hours=24):
    """Analyze job performance metrics"""
    print(f"\n⚙️ JOB METRICS ANALYSIS (Last {hours} hours)")
    print("=" * 50)
    
    since = datetime.now() - timedelta(hours=hours)
    since_str = since.strftime('%Y-%m-%d %H:%M:%S')
    
    # Get job metrics
    job_query = """
        SELECT tool, status, processing_time_ms, input_size_bytes, output_size_bytes, created_at
        FROM job_metrics 
        WHERE created_at >= ?
        ORDER BY created_at DESC
    """
    
    results = query_database(job_query, (since_str,))
    if not results:
        print("📊 No job metrics data found")
        return
    
    print(f"📊 Total jobs processed: {len(results)}")
    
    # Analyze by tool
    tool_stats = defaultdict(lambda: {'total': 0, 'success': 0, 'failed': 0, 'times': []})
    
    for row in results:
        tool = row['tool']
        status = row['status']
        processing_time = row['processing_time_ms']
        
        tool_stats[tool]['total'] += 1
        if status == 'SUCCESS':
            tool_stats[tool]['success'] += 1
        else:
            tool_stats[tool]['failed'] += 1
        
        if processing_time:
            tool_stats[tool]['times'].append(processing_time)
    
    print(f"\n🔧 Performance by Tool:")
    for tool, stats in sorted(tool_stats.items()):
        success_rate = (stats['success'] / stats['total']) * 100 if stats['total'] > 0 else 0
        avg_time = sum(stats['times']) / len(stats['times']) if stats['times'] else 0
        
        print(f"   {tool}:")
        print(f"     📊 {stats['total']} total ({stats['success']} success, {stats['failed']} failed)")
        print(f"     ✅ {success_rate:.1f}% success rate")
        if avg_time > 0:
            print(f"     ⏱️  {avg_time/1000:.2f}s average processing time")

def analyze_usage_patterns(hours=168):
    """Analyze overall usage patterns"""
    print(f"\n📈 USAGE PATTERNS ANALYSIS (Last {hours} hours)")
    print("=" * 50)
    
    since = datetime.now() - timedelta(hours=hours)
    since_str = since.strftime('%Y-%m-%d %H:%M:%S')
    
    # Get all API logs
    usage_query = """
        SELECT timestamp, ip, path, method
        FROM api_log 
        WHERE timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 1000
    """
    
    results = query_database(usage_query, (since_str,))
    if not results:
        print("📊 No usage data found")
        return
    
    print(f"📊 Total API requests: {len(results)}")
    
    # Unique users
    unique_ips = len(set(row['ip'] for row in results))
    print(f"👥 Unique IPs: {unique_ips}")
    
    # Most active endpoints
    endpoint_counts = Counter(row['path'] for row in results)
    print(f"\n🔥 Most Popular Endpoints:")
    for endpoint, count in endpoint_counts.most_common(10):
        print(f"   {endpoint}: {count}")
    
    # Most active users
    ip_counts = Counter(row['ip'] for row in results)
    print(f"\n👑 Most Active Users (by IP):")
    for ip, count in ip_counts.most_common(10):
        print(f"   {ip}: {count} requests")

def main():
    """Main analysis function"""
    print("🌐 EasyGIFMaker Local Usage Analysis")
    print(f"📅 Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Check if database exists
    db_path = get_db_path()
    if not db_path:
        print("\n⚠️  Cannot proceed without database access")
        return
    
    print(f"📍 Using database: {db_path}")
    
    # Run different analyses
    analyze_ai_usage(24)      # Last 24 hours AI usage
    analyze_job_metrics(24)   # Last 24 hours job performance
    analyze_usage_patterns(168)  # Last week overall patterns
    
    print(f"\n✅ Analysis completed!")
    print(f"\n💡 Tips:")
    print(f"   - AI endpoints: /ai/convert, /ai/add-text")
    print(f"   - Monitor success rates for performance issues")
    print(f"   - Check for unusual usage patterns or potential abuse")
    print(f"   - Use job metrics to optimize processing times")

if __name__ == "__main__":
    main()
