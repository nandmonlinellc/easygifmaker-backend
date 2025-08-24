#!/bin/bash
# 🚀 EasyGIFMaker API Dashboard Launcher
# One command to rule them all!

echo "🚀 Starting EasyGIFMaker AI API Dashboard..."
echo "📁 Navigating to API directory..."

cd /Users/muhammadnazam/Documents/video-to-gif2/easygifmaker_api

echo "🐍 Activating virtual environment..."
source venv/bin/activate

echo "🌐 Starting web dashboard..."
echo "📊 Dashboard will be available at: http://localhost:5555"
echo "💡 Press Ctrl+C to stop"
echo ""

python simple_web_dashboard.py
