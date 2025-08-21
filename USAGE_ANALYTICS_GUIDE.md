# 🌐 EasyGIFMaker Usage Analytics Guide

## 📋 Overview
This guide contains all commands and information for monitoring API usage, especially AI endpoints (`/ai/convert` and `/ai/add-text`).

## 🔧 Available Analytics Tools

### 1. **Local Database Analysis** (Recommended)
Direct database query without web server - fastest method.

```bash
# Basic usage analysis
python3 local_usage_check.py

# Make executable (one time setup)
chmod +x local_usage_check.py
./local_usage_check.py
```

**What it shows:**
- 🤖 AI endpoint usage (last 24 hours)
- ⚙️ Job metrics and performance (last 24 hours) 
- 📈 Overall usage patterns (last 7 days)
- 👥 User analysis by IP address
- 🔧 User agent analysis

### 2. **Web Dashboard** (Admin Only)
Web-based dashboard with admin authentication.

```bash
# Set admin token and run
export ADMIN_TOKEN=your_secret_admin_token
python3 api_usage_dashboard.py

# Or run with token inline
ADMIN_TOKEN=your_secret_token python3 api_usage_dashboard.py
```

**Features:**
- Real-time web interface
- Admin authentication required
- Comprehensive statistics
- User behavior analysis

### 3. **Admin Web Endpoints** (Server Required)
When Flask server is running, access admin endpoints directly.

```bash
# Server must be running first
python3 src/main.py

# Then access these URLs (with admin token):
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:5000/admin/ai-usage
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:5000/admin/api-stats
curl -H "Authorization: Bearer $ADMIN_TOKEN" http://localhost:5000/admin/user-analysis
```

## 🧪 Testing & Development

### Generate Test Data
```bash
# Insert 25 random AI usage records
python3 test_ai_usage.py

# Then analyze the test data
python3 local_usage_check.py
```

### Clear Test Data
```bash
# Remove test AI usage data (be careful!)
sqlite3 instance/app.db "DELETE FROM api_log WHERE path LIKE '/ai/%' AND ip IN ('192.168.1.100', '10.0.0.50', '203.45.67.89', '172.16.0.10');"
```

## �� Understanding the Data

### AI Usage Metrics
- **Total AI requests**: Number of calls to AI endpoints
- **Requests by endpoint**: Breakdown of `/ai/convert` vs `/ai/add-text`
- **Top IPs**: Most active users by IP address
- **User agents**: Browser vs API tool vs script usage

### Job Performance Metrics
- **Success rate**: Percentage of successful jobs
- **Processing time**: Average time per tool
- **Tool usage**: Which GIF tools are most popular

### Usage Patterns
- **Unique users**: Count of different IP addresses
- **Popular endpoints**: Most requested API endpoints
- **Active users**: Heavy usage patterns

## 🔐 Security & Authentication

### Admin Token Setup
```bash
# Set permanent admin token in environment
echo 'export ADMIN_TOKEN=your_secret_admin_token_here' >> ~/.zshrc
source ~/.zshrc

# Or create .env file
echo "ADMIN_TOKEN=your_secret_admin_token_here" > .env
```

### Database Security
- Database location: `instance/app.db`
- Direct access: `sqlite3 instance/app.db`
- Backup: `cp instance/app.db instance/app.db.backup`

## 📅 Regular Monitoring Commands

### Daily Check
```bash
# Quick daily usage summary
python3 local_usage_check.py | head -20
```

### Weekly Report
```bash
# Full weekly analysis with timestamp
echo "=== Weekly Usage Report $(date) ===" > weekly_report.txt
python3 local_usage_check.py >> weekly_report.txt
```

### Real-time Monitoring
```bash
# Watch for new AI usage (update every 30 seconds)
watch -n 30 'python3 local_usage_check.py | grep -A 10 "AI USAGE ANALYSIS"'
```

## 🚨 Alert Commands

### Check for Heavy Usage
```bash
# Alert if more than 50 AI requests in last hour
AI_COUNT=$(sqlite3 instance/app.db "SELECT COUNT(*) FROM api_log WHERE path LIKE '/ai/%' AND datetime(timestamp) >= datetime('now', '-1 hour');")
if [ "$AI_COUNT" -gt 50 ]; then
    echo "⚠️  ALERT: $AI_COUNT AI requests in last hour!"
fi
```

### Monitor Specific IP
```bash
# Check usage for specific IP address
IP_TO_MONITOR="192.168.1.100"
sqlite3 instance/app.db "SELECT COUNT(*), path FROM api_log WHERE ip='$IP_TO_MONITOR' AND datetime(timestamp) >= datetime('now', '-1 day') GROUP BY path;"
```

## 📁 File Locations

- **Main analytics script**: `local_usage_check.py`
- **Web dashboard**: `api_usage_dashboard.py` 
- **Test data generator**: `test_ai_usage.py`
- **Database**: `instance/app.db`
- **Flask main**: `src/main.py`
- **This guide**: `USAGE_ANALYTICS_GUIDE.md`

## 🎯 Quick Reference

| Task | Command |
|------|---------|
| Check AI usage | `python3 local_usage_check.py` |
| Generate test data | `python3 test_ai_usage.py` |
| Web dashboard | `ADMIN_TOKEN=xxx python3 api_usage_dashboard.py` |
| Database backup | `cp instance/app.db instance/backup_$(date +%Y%m%d).db` |
| Clear test data | See "Clear Test Data" section above |

---
📅 **Last Updated**: August 21, 2025
🔧 **Version**: 1.0
👨‍💻 **Created for**: EasyGIFMaker API Usage Monitoring

## 🔍 Data Verification

### Check Data Authenticity
```bash
# Verify if current data is real or test data
python3 data_verification.py
```

### Current Data Status (as of August 21, 2025)
- **AI Usage Data**: TEST DATA ONLY (25 test requests)
- **Job Metrics**: REAL USER DATA (18 actual jobs processed)
- **Test IPs**: `192.168.1.100`, `10.0.0.50`, `203.45.67.89`, `172.16.0.10`

### Clean Database for Production
```bash
# Remove all test data to start fresh monitoring
sqlite3 instance/app.db "DELETE FROM api_log WHERE ip IN ('192.168.1.100', '10.0.0.50', '203.45.67.89', '172.16.0.10');"

# Verify cleanup
python3 data_verification.py
```

## 📋 Available Scripts Summary

| Script | Purpose | Data Type |
|--------|---------|-----------|
| `local_usage_check.py` | Main analytics dashboard | Real + Test |
| `api_usage_dashboard.py` | Web-based admin dashboard | Real + Test |
| `test_ai_usage.py` | Generate test AI usage data | Test Only |
| `data_verification.py` | Check real vs test data | Analysis |
| `USAGE_ANALYTICS_GUIDE.md` | This documentation | Guide |

---
🔄 **Updated**: August 21, 2025 - Added data verification section
