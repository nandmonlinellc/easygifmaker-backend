import os
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

# Debug: Print broker and backend URLs at startup
print(f"[Celery Debug] broker_url: {celery.conf.broker_url}")
print(f"[Celery Debug] result_backend: {celery.conf.result_backend}")

# Import the Flask app module so that it can configure Celery with Flask app context
# (create_app() in main.py calls configure_celery(app, celery))
try:
	from src import main as _flask_main  # noqa: F401
except Exception as _e:
	# In some tooling contexts this may fail; worker can still run but DB ops may lack app context
	print(f"[Celery Debug] Warning: failed to import Flask app for Celery context: {_e}")

# Import tasks to register them with Celery (after app import)
from src import tasks  # noqa: F401