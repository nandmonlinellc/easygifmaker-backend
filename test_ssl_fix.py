#!/usr/bin/env python3

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from src.config import fix_redis_ssl_url, DevelopmentConfig, ProductionConfig

# Test the fix_redis_ssl_url function
test_url = "rediss://default:841f3b3ae783475581d8a46b9b4e8c0e@fly-easygifmaker-redis.upstash.io:6379"
fixed_url = fix_redis_ssl_url(test_url)

print(f"Original URL: {test_url}")
print(f"Fixed URL: {fixed_url}")
print(f"Function working: {'ssl_cert_reqs=CERT_NONE' in fixed_url}")

# Test class methods
print(f"\nTesting class methods:")
print(f"ProductionConfig.get_celery_broker_url(): {ProductionConfig.get_celery_broker_url()}")
print(f"ProductionConfig.get_celery_result_backend(): {ProductionConfig.get_celery_result_backend()}")

# Set environment variables for testing
os.environ['REDIS_URL'] = test_url
print(f"\nAfter setting REDIS_URL env var:")
print(f"ProductionConfig.get_celery_broker_url(): {ProductionConfig.get_celery_broker_url()}")
print(f"ProductionConfig.get_celery_result_backend(): {ProductionConfig.get_celery_result_backend()}")
