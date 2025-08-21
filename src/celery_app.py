import os
import logging
from celery import Celery

def fix_redis_ssl_url(url):
    """Add SSL cert requirements to rediss:// URLs if missing"""
    if url and url.startswith('rediss://') and 'ssl_cert_reqs' not in url:
        # Add CERT_NONE for managed Redis services like Upstash
        separator = '&' if '?' in url else '?'
        return f"{url}{separator}ssl_cert_reqs=CERT_NONE"
    return url

def get_celery_urls():
    """Get properly configured Celery URLs with SSL fixes"""
    redis_url = os.environ.get('REDIS_URL')
    broker_url = os.environ.get('CELERY_BROKER_URL') or redis_url or 'redis://localhost:6379/0'
    backend_url = os.environ.get('CELERY_RESULT_BACKEND') or redis_url or 'redis://localhost:6379/0'
    
    return fix_redis_ssl_url(broker_url), fix_redis_ssl_url(backend_url)

# Only instantiate Celery here. Do NOT configure broker/backend or load config.
celery = Celery('easygifmaker_api')

# --- Ensure Celery is configured when run as a worker entrypoint ---
from src.config import DevelopmentConfig, ProductionConfig
config_class = ProductionConfig if os.environ.get('FLASK_ENV') == 'production' else DevelopmentConfig
celery.config_from_object(config_class)
# Explicitly set broker_url and result_backend for Celery with SSL fix
broker_url, result_backend = get_celery_urls()
celery.conf.broker_url = broker_url
celery.conf.result_backend = result_backend

# Add task timeout configurations for long-running video processing
celery.conf.task_soft_time_limit = 300  # 5 minutes soft timeout
celery.conf.task_time_limit = 600       # 10 minutes hard timeout
celery.conf.worker_prefetch_multiplier = 1  # Process one task at a time
celery.conf.task_acks_late = True       # Acknowledge after task completion
celery.conf.worker_disable_rate_limits = True  # Disable rate limiting for processing
# Debug: Log broker and backend URLs at startup
logging.debug("[Celery Debug] broker_url: %s", celery.conf.broker_url)
logging.debug(
    "[Celery Debug] result_backend: %s", celery.conf.result_backend
)

# Do not import the Flask app or tasks here: importing `src.main` or `src.tasks`
# at module import time can create a circular import (celery_app -> main -> celery_app).
# The Flask app will call `configure_celery(app, celery)` and import tasks after
# Celery is configured. Keeping this module minimal avoids circular import issues.
