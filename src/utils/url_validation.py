import os
import socket
import ipaddress
from urllib.parse import urlparse

ALLOWED_URL_HOSTS = [h.strip().lower() for h in os.environ.get('ALLOWED_URL_HOSTS', '').split(',') if h.strip()]

def _is_global_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_global
    except ValueError:
        return False

def validate_remote_url(url: str) -> str:
    """Validate that the given URL is safe for outbound HTTP requests."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("Only http and https URLs are allowed")
    if not parsed.hostname:
        raise ValueError("URL must include a hostname")
    host = parsed.hostname.lower()
    if ALLOWED_URL_HOSTS and host not in ALLOWED_URL_HOSTS:
        raise ValueError("Host is not allowed")
    try:
        addr_info = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise ValueError("Unable to resolve host")
    ips = {info[4][0] for info in addr_info}
    for ip in ips:
        if not _is_global_ip(ip):
            raise ValueError("IP address is not allowed")
    return url
