"""
Rate limiter configuration
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Create the limiter instance
limiter = Limiter(key_func=get_remote_address, default_limits=["200 per minute"])
