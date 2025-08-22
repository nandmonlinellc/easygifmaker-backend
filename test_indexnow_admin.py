#!/usr/bin/env python3
"""Lightweight tests for IndexNow admin endpoints using Flask test client.
Run: python test_indexnow_admin.py
Designed to avoid real network submissions (dry_run or monkeypatched).
"""
import os
import json

# Ensure admin token is set before importing app
os.environ.setdefault('ADMIN_TOKEN', 'testtoken')
os.environ.setdefault('FLASK_ENV', 'development')

from src.main import app  # noqa: E402

# Monkeypatch requests.post inside IndexNow utils to avoid network when NOT dry_run (sitemap)
import types
import src.utils.indexnow as indexnow_mod  # noqa: E402

class _DummyResp:
    def __init__(self, code=200):
        self.status_code = code

    @property
    def text(self):
        return ''

def _dummy_post(*args, **kwargs):
    return _DummyResp(200)

indexnow_mod.requests.post = _dummy_post  # type: ignore

client = app.test_client()
HEADERS = {'Authorization': 'Bearer testtoken'}

failures = 0

def check(condition, label, detail=None):
    global failures
    if condition:
        print(f"✅ {label}")
    else:
        failures += 1
        print(f"❌ {label}" + (f" :: {detail}" if detail else ""))

print("\n=== Testing /admin/indexnow/submit (dry_run) ===")
resp = client.post('/admin/indexnow/submit', json={'dry_run': True}, headers=HEADERS)
check(resp.status_code == 200, 'submit dry_run status 200', f"got {resp.status_code}")
if resp.is_json:
    data = resp.get_json()
    check(data.get('status') == 'dry_run', 'status is dry_run', data)
    check(data.get('count', 0) > 5, 'returned >5 URLs', data.get('count'))
else:
    check(False, 'JSON response expected')

print("\n=== Testing /admin/indexnow/submit with custom URLs (dry_run) ===")
custom_urls = ['https://easygifmaker.com/', 'https://easygifmaker.com/video-to-gif']
resp = client.post('/admin/indexnow/submit', json={'dry_run': True, 'urls': custom_urls}, headers=HEADERS)
check(resp.status_code == 200, 'custom submit dry_run status 200', f"got {resp.status_code}")
if resp.is_json:
    data = resp.get_json()
    check(data.get('count') == len(custom_urls), 'count equals custom list length', data.get('count'))
else:
    check(False, 'JSON response expected (custom)')

print("\n=== Testing /admin/indexnow/sitemap ===")
resp = client.post('/admin/indexnow/sitemap', headers=HEADERS)
check(resp.status_code == 200, 'sitemap status 200', f"got {resp.status_code}")
if resp.is_json:
    data = resp.get_json()
    check('url' in data, 'sitemap response contains url field')
else:
    check(False, 'JSON response expected (sitemap)')

print("\n=== SUMMARY ===")
if failures == 0:
    print("All IndexNow admin endpoint tests passed ✅")
    exit(0)
else:
    print(f"{failures} failures ❌")
    exit(1)
