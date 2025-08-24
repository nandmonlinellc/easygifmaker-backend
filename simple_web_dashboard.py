#!/usr/bin/env python3
"""
🚀 EasyGIFMaker AI API Simple Web Dashboard
Fixed version with working template
"""

from flask import Flask, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)

def get_database_path():
    """Get the database path"""
    db_path = "instance/app.db"
    if not os.path.exists(db_path):
        return None
    return db_path

def get_api_stats():
    """Get API statistics"""
    db_path = get_database_path()
    if not db_path:
        return None
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Basic stats
    cursor.execute("""
        SELECT COUNT(*) as total_requests,
               COUNT(DISTINCT ip) as unique_users
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
    """)
    basic_stats = cursor.fetchone()
    
    # Endpoint stats
    cursor.execute("""
        SELECT path, COUNT(*) as requests, COUNT(DISTINCT ip) as users
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
        GROUP BY path
        ORDER BY requests DESC
    """)
    endpoints = cursor.fetchall()
    
    # Top users
    cursor.execute("""
        SELECT ip, COUNT(*) as requests
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
        GROUP BY ip
        ORDER BY requests DESC
        LIMIT 10
    """)
    top_users = cursor.fetchall()
    
    # Recent activity
    cursor.execute("""
        SELECT timestamp, ip, path
        FROM api_log 
        WHERE path LIKE '/api/ai/%' OR path LIKE '/ai/%'
        ORDER BY timestamp DESC
        LIMIT 10
    """)
    recent_activity = cursor.fetchall()
    
    conn.close()
    
    return {
        'basic_stats': basic_stats,
        'endpoints': endpoints,
        'top_users': top_users,
        'recent_activity': recent_activity,
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

@app.route('/')
def dashboard():
    """Simple dashboard page"""
    stats = get_api_stats()
    if not stats:
        return "Database not found. Make sure the API has been used and logged requests.", 404
    
    # Build endpoint bars
    endpoint_bars = ""
    if stats['endpoints']:
        total_requests = stats['basic_stats'][0]
        for endpoint, requests, users in stats['endpoints']:
            percentage = (requests / total_requests * 100) if total_requests > 0 else 0
            bar_width = int(percentage * 2)  # Scale for visual
            endpoint_bars += f"""
                <div style="margin-bottom: 15px;">
                    <div style="display: flex; justify-content: space-between; margin-bottom: 5px;">
                        <span style="font-family: monospace; background: #e9ecef; padding: 2px 6px; border-radius: 4px;">{endpoint}</span>
                        <span><strong>{requests:,}</strong> requests • <strong>{users}</strong> users</span>
                    </div>
                    <div style="background: linear-gradient(90deg, #4facfe, #00f2fe); height: 20px; border-radius: 10px; width: {bar_width}%; display: flex; align-items: center; color: white; padding: 0 10px; font-size: 0.9em; font-weight: 600; min-width: 60px;">
                        {percentage:.1f}%
                    </div>
                </div>
            """
    
    # Build users table
    users_table = ""
    for i, (ip, requests) in enumerate(stats['top_users'][:5], 1):
        users_table += f"""
            <tr>
                <td><strong>#{i}</strong></td>
                <td style="font-family: monospace; color: #495057;">{ip}</td>
                <td><span style="color: #28a745; font-weight: 600;">{requests}</span></td>
            </tr>
        """
    
    # Build recent activity table
    activity_table = ""
    for timestamp, ip, path in stats['recent_activity'][:8]:
        time_str = timestamp[5:16] if len(timestamp) > 16 else timestamp  # MM-DD HH:MM
        activity_table += f"""
            <tr>
                <td>{time_str}</td>
                <td style="font-family: monospace; color: #495057;">{ip}</td>
                <td style="font-family: monospace; background: #e9ecef; padding: 2px 6px; border-radius: 4px;">{path}</td>
            </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>🤖 EasyGIFMaker AI API Dashboard</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
                min-height: 100vh;
            }}
            .container {{ 
                max-width: 1200px; 
                margin: 0 auto; 
                background: white;
                border-radius: 15px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.2);
                overflow: hidden;
            }}
            .header {{
                background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{ margin: 0; font-size: 2.5em; text-shadow: 2px 2px 4px rgba(0,0,0,0.3); }}
            .header p {{ margin: 10px 0 0 0; opacity: 0.9; }}
            .content {{ padding: 30px; }}
            .stats-grid {{ 
                display: grid; 
                grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); 
                gap: 20px; 
                margin-bottom: 30px; 
            }}
            .stat-card {{ 
                background: #f8f9fa; 
                padding: 20px; 
                border-radius: 10px; 
                border-left: 5px solid #4facfe;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #4facfe; margin-bottom: 5px; }}
            .stat-label {{ color: #666; text-transform: uppercase; font-size: 0.9em; letter-spacing: 1px; }}
            .section {{ 
                margin-bottom: 40px; 
                background: #f8f9fa;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            .section-header {{ 
                background: #4facfe; 
                color: white; 
                padding: 15px 20px; 
                font-weight: bold;
                font-size: 1.1em;
            }}
            .section-content {{ padding: 20px; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
            th {{ background: #f1f3f4; font-weight: 600; }}
            tr:hover {{ background: #f8f9fa; }}
            .refresh-btn {{
                position: fixed;
                top: 20px;
                right: 20px;
                background: #28a745;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 25px;
                cursor: pointer;
                box-shadow: 0 2px 10px rgba(0,0,0,0.2);
                font-weight: 600;
                z-index: 1000;
            }}
            .refresh-btn:hover {{ background: #218838; transform: translateY(-2px); }}
        </style>
    </head>
    <body>
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh</button>
        
        <div class="container">
            <div class="header">
                <h1>🤖 EasyGIFMaker AI API Dashboard</h1>
                <p>Real-time analytics and usage insights • Generated: {stats['generated_at']}</p>
            </div>
            
            <div class="content">
                <!-- Overview Stats -->
                <div class="stats-grid">
                    <div class="stat-card">
                        <div class="stat-number">{stats['basic_stats'][0]:,}</div>
                        <div class="stat-label">Total Requests</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{stats['basic_stats'][1]}</div>
                        <div class="stat-label">Unique Users</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{len(stats['endpoints'])}</div>
                        <div class="stat-label">Active Endpoints</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-number">{len(stats['recent_activity'])}</div>
                        <div class="stat-label">Recent Activities</div>
                    </div>
                </div>

                <!-- Endpoint Usage -->
                <div class="section">
                    <div class="section-header">🎯 Most Popular Endpoints</div>
                    <div class="section-content">
                        {endpoint_bars}
                    </div>
                </div>

                <!-- Top Users -->
                <div class="section">
                    <div class="section-header">👥 Most Active Users</div>
                    <div class="section-content">
                        <table>
                            <thead>
                                <tr>
                                    <th>Rank</th>
                                    <th>IP Address</th>
                                    <th>Requests</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users_table}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Recent Activity -->
                <div class="section">
                    <div class="section-header">🕐 Recent Activity</div>
                    <div class="section-content">
                        <table>
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>IP Address</th>
                                    <th>Endpoint</th>
                                </tr>
                            </thead>
                            <tbody>
                                {activity_table}
                            </tbody>
                        </table>
                    </div>
                </div>

                <!-- Footer -->
                <div style="text-align: center; padding: 20px; color: #666; border-top: 1px solid #ddd; margin-top: 30px;">
                    <p>🚀 <strong>EasyGIFMaker AI API</strong> is performing well! Keep up the great work.</p>
                    <p><small>Dashboard updates in real-time • Last update: {stats['generated_at']}</small></p>
                </div>
            </div>
        </div>

        <script>
            // Auto-refresh every 60 seconds
            setTimeout(() => location.reload(), 60000);
        </script>
    </body>
    </html>
    """
    
    return html

@app.route('/api/stats')
def api_stats():
    """API endpoint for getting stats as JSON"""
    stats = get_api_stats()
    if not stats:
        return jsonify({"error": "Database not found"}), 404
    
    return jsonify({
        'total_requests': stats['basic_stats'][0],
        'unique_users': stats['basic_stats'][1],
        'endpoints': [{'path': e[0], 'requests': e[1], 'users': e[2]} for e in stats['endpoints']],
        'top_users': [{'ip': u[0], 'requests': u[1]} for u in stats['top_users'][:5]],
        'generated_at': stats['generated_at']
    })

if __name__ == '__main__':
    print("🚀 Starting EasyGIFMaker AI API Dashboard...")
    print("📊 Dashboard will be available at: http://localhost:5555")
    print("📡 API stats endpoint: http://localhost:5555/api/stats")
    print("🔄 Auto-refreshes every 60 seconds")
    print()
    print("💡 Press Ctrl+C to stop")
    
    app.run(host='0.0.0.0', port=5555, debug=False)
