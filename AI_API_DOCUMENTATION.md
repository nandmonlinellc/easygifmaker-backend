# 🚀 EasyGIFMaker AI API Documentation

## Overview

The EasyGIFMaker AI API provides professional GIF creation and editing tools accessible to AI agents, automation platforms, and developers. This API is designed to be easily consumable by ChatGPT, Perplexity, Zapier, and other AI platforms.

## Base URL

```
https://easygifmaker-api.fly.dev
```

## Authentication

Currently, the API is open access. Rate limiting is applied to prevent abuse.

## Endpoints

### 1. Health Check

**GET** `/api/ai/health`

Check if the AI API is operational.

**Response:**
```json
{
  "status": "healthy",
  "service": "EasyGIFMaker AI API",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "version": "1.0.0"
}
```

### 2. API Capabilities

**GET** `/api/ai/capabilities`

Get comprehensive API documentation for AI agents.

**Response:**
```json
{
  "service": "EasyGIFMaker AI API",
  "description": "Professional GIF creation and editing tools accessible to AI agents",
  "version": "1.0.0",
  "endpoints": {
    "/api/ai/convert": {
      "method": "POST",
      "description": "Convert video to GIF",
      "input_types": ["url", "base64_data", "file"],
      "parameters": ["fps", "quality", "max_width", "max_height", "start_time", "duration"]
    }
  },
  "supported_formats": {
    "input_video": ["mp4", "avi", "mov", "webm", "mkv", "flv"],
    "input_images": ["png", "jpg", "jpeg", "gif", "bmp", "webp", "apng"],
    "output": ["gif"]
  },
  "rate_limits": {
    "requests_per_minute": 60,
    "file_size_limit_mb": 50
  }
}
```

### 3. Convert Video to GIF

**POST** `/api/ai/convert`

Convert a video file to GIF format.

**Input Types:**
- **URL**: Direct URL to video file
- **Base64**: Base64 encoded video data
- **File Upload**: Multipart form file upload

**Parameters:**
- `fps` (optional): Frames per second (default: 10)
- `quality` (optional): high/medium/low (default: high)
- `max_width` (optional): Maximum width in pixels (default: 480)
- `max_height` (optional): Maximum height in pixels (default: 480)
- `start_time` (optional): Start time in seconds (default: 0)
- `duration` (optional): Duration in seconds

**Example Request (URL):**
```json
{
  "url": "https://example.com/video.mp4",
  "fps": 15,
  "quality": "high",
  "max_width": 640,
  "max_height": 480
}
```

**Example Request (Base64):**
```json
{
  "base64_data": "data:video/mp4;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuBzvLZiTYIG2m98OScTgwOUarm7blmGgU7k9n1unEiBC13yO/eizEIHWq+8+OWT...",
  "fps": 10,
  "quality": "medium"
}
```

**Response:**
```json
{
  "success": true,
  "task_id": "abc123-def456-ghi789",
  "status": "processing",
  "message": "Video conversion started",
  "api_endpoints": {
    "check_status": "/api/ai/status/abc123-def456-ghi789",
    "download_result": "/api/ai/download/abc123-def456-ghi789"
  }
}
```

### 4. Create GIF from Images

**POST** `/api/ai/create-gif`

Create a GIF animation from multiple images.

**Input Types:**
- **URLs**: List of image URLs
- **Base64**: List of base64 encoded images
- **File Uploads**: Multiple multipart form file uploads

**Parameters:**
- `fps` (optional): Frames per second (default: 10)
- `quality` (optional): high/medium/low (default: high)
- `loop` (optional): Loop animation (default: true)

**Example Request (URLs):**
```json
{
  "urls": [
    "https://example.com/image1.png",
    "https://example.com/image2.png",
    "https://example.com/image3.png"
  ],
  "fps": 15,
  "quality": "high",
  "loop": true
}
```

**Example Request (Base64):**
```json
{
  "base64_images": [
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
  ],
  "fps": 10,
  "quality": "medium"
}
```

### 5. Optimize GIF

**POST** `/api/ai/optimize`

Optimize GIF file size while maintaining quality.

**Input Types:**
- **URL**: Direct URL to GIF file
- **Base64**: Base64 encoded GIF data
- **File Upload**: Multipart form file upload

**Parameters:**
- `target_size_mb` (optional): Target file size in MB (default: 5)
- `quality` (optional): high/medium/low (default: high)

**Example Request:**
```json
{
  "url": "https://example.com/large.gif",
  "target_size_mb": 3,
  "quality": "high"
}
```

### 6. Add Text to GIF

**POST** `/api/ai/add-text`

Add text overlay to a GIF.

**Input Types:**
- **URL**: Direct URL to GIF file
- **Base64**: Base64 encoded GIF data
- **File Upload**: Multipart form file upload

**Parameters:**
- `text` (required): Text to add
- `font_size` (optional): Font size in pixels (default: 24)
- `font_color` (optional): Font color in hex (default: #FFFFFF)
- `position` (optional): top/bottom/center (default: bottom)
- `x_offset` (optional): Horizontal offset (default: 0)
- `y_offset` (optional): Vertical offset (default: 0)

**Example Request:**
```json
{
  "url": "https://example.com/animation.gif",
  "text": "Hello World!",
  "font_size": 32,
  "font_color": "#FF0000",
  "position": "bottom",
  "x_offset": 0,
  "y_offset": 10
}
```

### 7. Check Task Status

**GET** `/api/ai/status/{task_id}`

Check the status of an asynchronous task.

**Response (Processing):**
```json
{
  "success": true,
  "status": "processing",
  "task_id": "abc123-def456-ghi789",
  "message": "Task is still processing"
}
```

**Response (Completed):**
```json
{
  "success": true,
  "status": "completed",
  "task_id": "abc123-def456-ghi789",
  "result": {
    "output_path": "/path/to/output.gif",
    "file_size_mb": 2.5
  },
  "download_url": "/api/ai/download/abc123-def456-ghi789"
}
```

**Response (Failed):**
```json
{
  "success": false,
  "status": "failed",
  "task_id": "abc123-def456-ghi789",
  "error": "Invalid video format"
}
```

### 8. Download Result

**GET** `/api/ai/download/{task_id}`

Download the result file from a completed task.

**Response:** Binary file download

## Error Handling

All endpoints return structured error responses with helpful messages and usage information.

**Example Error Response:**
```json
{
  "error": "No video input provided. Please provide url, base64_data, or file upload.",
  "usage": {
    "url": "Direct URL to video file",
    "base64_data": "Base64 encoded video data",
    "file": "Multipart form file upload",
    "parameters": {
      "fps": "Frames per second (default: 10)",
      "quality": "high/medium/low (default: high)"
    }
  }
}
```

## Rate Limits

- **Requests per minute**: 60
- **File size limit**: 50 MB
- **Supported formats**: MP4, AVI, MOV, WebM, MKV, FLV, PNG, JPG, JPEG, GIF, BMP, WebP, APNG

## Usage Examples

### ChatGPT Browsing Mode
```python
import requests

# Convert video to GIF
response = requests.post('https://easygifmaker-api.fly.dev/api/ai/convert', json={
    'url': 'https://example.com/video.mp4',
    'fps': 10,
    'quality': 'high'
})

task_id = response.json()['task_id']

# Check status
status_response = requests.get(f'https://easygifmaker-api.fly.dev/api/ai/status/{task_id}')
if status_response.json()['status'] == 'completed':
    # Download result
    download_response = requests.get(f'https://easygifmaker-api.fly.dev/api/ai/download/{task_id}')
    with open('output.gif', 'wb') as f:
        f.write(download_response.content)
```

### Perplexity AI Agent
```python
# Create GIF from images
response = requests.post('https://easygifmaker-api.fly.dev/api/ai/create-gif', json={
    'urls': [
        'https://example.com/image1.png',
        'https://example.com/image2.png',
        'https://example.com/image3.png'
    ],
    'fps': 15,
    'quality': 'high'
})
```

### Zapier Automation
```python
# Optimize GIF for social media
response = requests.post('https://easygifmaker-api.fly.dev/api/ai/optimize', json={
    'url': 'https://example.com/large.gif',
    'target_size_mb': 5,
    'quality': 'high'
})
```

## Integration Benefits

✅ **AI Agent Access**: ChatGPT, Perplexity can use your tools  
✅ **Multiple Input Types**: URL, base64, file upload  
✅ **Async Processing**: Handle large files efficiently  
✅ **Rich Documentation**: Self-documenting API  
✅ **Error Handling**: Comprehensive error messages  
✅ **Rate Limiting**: Protect against abuse  

## Expected Results

1. **ChatGPT Integration**: AI can create GIFs during conversations
2. **Perplexity Integration**: AI agents can use your tools
3. **Zapier Automation**: Automated GIF processing workflows
4. **Increased Usage**: More users through AI platforms
5. **Revenue Growth**: More conversions from AI referrals

Your GIF tools will now be accessible to AI agents worldwide! 🎉 