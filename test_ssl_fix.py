import os
from src.config import fix_redis_ssl_url, ProductionConfig


def test_fix_redis_ssl_url():
    test_url = "rediss://default:841f3b3ae783475581d8a46b9b4e8c0e@fly-easygifmaker-redis.upstash.io:6379"
    fixed_url = fix_redis_ssl_url(test_url)
    assert "ssl_cert_reqs=CERT_NONE" in fixed_url, "Missing ssl_cert_reqs parameter"


def test_production_config_uses_fixed_url(monkeypatch):
    test_url = "rediss://default:841f3b3ae783475581d8a46b9b4e8c0e@fly-easygifmaker-redis.upstash.io:6379"
    monkeypatch.setenv("REDIS_URL", test_url)
    expected = fix_redis_ssl_url(test_url)
    assert ProductionConfig.get_celery_broker_url() == expected, "Broker URL not fixed"
    assert ProductionConfig.get_celery_result_backend() == expected, "Backend URL not fixed"
