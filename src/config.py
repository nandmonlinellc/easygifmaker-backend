import os
from datetime import timedelta

def fix_redis_ssl_url(url):
    """Add SSL cert requirements to rediss:// URLs if missing"""
    if url and url.startswith('rediss://') and 'ssl_cert_reqs' not in url:
        # Add CERT_NONE for managed Redis services like Upstash
        separator = '&' if '?' in url else '?'
        return f"{url}{separator}ssl_cert_reqs=CERT_NONE"
    return url

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'a_default_secret_key_for_development')
    MAX_CONTENT_LENGTH = 200 * 1024 * 1024  # 200MB max file size
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # For local development, you might use SQLite
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    # Use local directory for uploads in development, Fly.io Volume in production
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(os.getcwd(), 'uploads'))

    # Temporary file cleanup settings
    TEMP_FILE_MAX_AGE = int(os.environ.get('TEMP_FILE_MAX_AGE', 7200))  # seconds
    TEMP_FILE_CLEANUP_INTERVAL = int(os.environ.get('TEMP_FILE_CLEANUP_INTERVAL', 3600))  # seconds
    CELERY_BEAT_SCHEDULE = {
        "cleanup-old-temp-files": {
            "task": "tasks.cleanup_old_files",
            "schedule": timedelta(seconds=TEMP_FILE_CLEANUP_INTERVAL),
        }
    }
    
    @classmethod
    def get_celery_broker_url(cls):
        """Get Celery broker URL with SSL fix applied"""
        redis_url = os.environ.get('REDIS_URL')
        broker_url = os.environ.get('CELERY_BROKER_URL') or redis_url or 'redis://localhost:6379/0'
        return fix_redis_ssl_url(broker_url)
    
    @classmethod
    def get_celery_result_backend(cls):
        """Get Celery result backend URL with SSL fix applied"""
        redis_url = os.environ.get('REDIS_URL')
        backend_url = os.environ.get('CELERY_RESULT_BACKEND') or redis_url or 'redis://localhost:6379/0'
        return fix_redis_ssl_url(backend_url)
    
    # Legacy properties for backward compatibility
    @property
    def CELERY_BROKER_URL(self):
        return self.get_celery_broker_url()
    
    @property
    def CELERY_RESULT_BACKEND(self):
        return self.get_celery_result_backend()

class DevelopmentConfig(Config):
    DEBUG = True
    # Allow all origins in development
    CORS_ORIGINS = "*"

class ProductionConfig(Config):
    DEBUG = False
    # Restrict to your frontend domain in production
    CORS_ORIGINS = ["https://easygifmaker.com", "https://www.easygifmaker.com"]
