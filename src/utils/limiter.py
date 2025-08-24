"""
Rate limiter configuration
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import os

# Use Redis for rate limiting in production, memory for local dev
storage_uri = os.environ.get('REDIS_URL', 'memory://')

# Create the limiter instance
limiter = Limiter(
    key_func=get_remote_address, 
    default_limits=["200 per minute"],
    storage_uri=storage_uri
)
