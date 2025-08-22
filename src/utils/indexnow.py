import requests
import logging
from typing import List, Optional
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

class IndexNow:
    """IndexNow implementation for instant search engine indexing"""
    last_results: list = []  # populated after submit
    
    def __init__(self, api_key: str, site_url: str):
        self.api_key = api_key
        self.site_url = site_url.rstrip('/')
        self.endpoints = [
            "https://api.indexnow.org/indexnow",
            "https://www.bing.com/indexnow",
            "https://search.seznam.cz/indexnow",
            "https://searchbox.yandex.com/indexnow"
        ]
    
    def submit_url(self, url: str) -> bool:
        """Submit a single URL to IndexNow"""
        return self.submit_urls([url])
    
    def submit_urls(self, urls: List[str]) -> bool:
        """Submit multiple URLs to IndexNow and capture per-endpoint results"""
        self.last_results = []
        if not urls:
            return False
            
        # Convert relative URLs to absolute
        absolute_urls = []
        for url in urls:
            if url.startswith('/'):
                absolute_urls.append(f"{self.site_url}{url}")
            elif url.startswith(('http://', 'https://')):
                absolute_urls.append(url)
            else:
                absolute_urls.append(f"{self.site_url}/{url}")
        
        payload = {
            "host": self.site_url.replace('https://', '').replace('http://', ''),
            "key": self.api_key,
            "keyLocation": f"{self.site_url}/{self.api_key}.txt",
            "urlList": absolute_urls
        }
        
        success_count = 0
        for endpoint in self.endpoints:
            try:
                record = {"endpoint": endpoint}
                response = requests.post(
                    endpoint,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                
                if response.status_code in (200, 202):
                    record["status"] = response.status_code
                    record["ok"] = True
                    success_count += 1
                    logger.info(f"IndexNow: Successfully submitted {len(urls)} URLs to {endpoint}")
                else:
                    record["status"] = response.status_code
                    record["ok"] = False
                    self.last_results.append(record)
                    logger.warning(f"IndexNow: Failed to submit to {endpoint} - {response.status_code}")
                    
            except Exception as e:
                record["error"] = str(e)
                self.last_results.append(record)
                logger.error(f"IndexNow: Error submitting to {endpoint}: {e}")
        
        return success_count > 0

# Initialize IndexNow instance
def get_indexnow_client():
    """Get configured IndexNow client"""
    return IndexNow(
        api_key="7820a1cd5e434c278e39cfeb9ec3b008",
        site_url="https://easygifmaker.com"
    )

def notify_url_change(url: str):
    """Notify search engines of URL change"""
    try:
        client = get_indexnow_client()
        return client.submit_url(url)
    except Exception as e:
        logger.error(f"IndexNow notification failed: {e}")
        return False

def notify_urls_change(urls: List[str]):
    """Notify search engines of multiple URL changes"""
    try:
        client = get_indexnow_client()
        return client.submit_urls(urls)
    except Exception as e:
        logger.error(f"IndexNow bulk notification failed: {e}")
        return False
