"""Utilities for IndexNow submissions.

Provides a small client helper to submit URLs to search engines that
support the IndexNow protocol (e.g., Bing and Yandex).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Iterable
import os
import requests

# Search engines that currently support IndexNow
INDEXNOW_ENDPOINTS: List[str] = [
    "https://www.bing.com/indexnow",
    "https://yandex.com/indexnow",
]

# API key and site URL can be overridden via environment variables
API_KEY: str = os.environ.get("INDEXNOW_KEY", "6bada9110783450bb91db9e0fc88a08c")
SITE_URL: str = os.environ.get("SITE_URL", "https://easygifmaker.com")


@dataclass
class IndexNowClient:
    """Simple container for IndexNow configuration."""

    api_key: str
    site_url: str
    endpoints: List[str]


def get_indexnow_client() -> IndexNowClient:
    """Return the configured :class:`IndexNowClient`."""
    return IndexNowClient(api_key=API_KEY, site_url=SITE_URL, endpoints=INDEXNOW_ENDPOINTS)


def _submit(urls: Iterable[str]) -> bool:
    """Submit the given URLs to all endpoints. Returns True if all succeed."""
    payload = {"host": SITE_URL, "key": API_KEY, "urlList": list(urls)}
    success = True
    for endpoint in INDEXNOW_ENDPOINTS:
        try:
            resp = requests.post(endpoint, json=payload, timeout=10)
            success = success and resp.status_code == 200
        except Exception:
            success = False
    return success


def notify_url_change(url: str) -> bool:
    """Notify search engines that a single URL has changed."""
    return _submit([url])


def notify_urls_change(urls: List[str]) -> bool:
    """Notify search engines that multiple URLs have changed."""
    return _submit(urls)
