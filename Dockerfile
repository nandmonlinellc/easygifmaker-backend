# Final Dockerfile for Fly.io - Flask + Celery + Gunicorn

# Use a minimal base image
FROM python:3.10-slim

# Environment configuration
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev bash ffmpeg gifsicle \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# Copy application source code
COPY . .

# Use a shell script to start both Gunicorn and Celery in the same container
COPY start.sh /start.sh
RUN chmod +x /start.sh
CMD ["/start.sh"]
