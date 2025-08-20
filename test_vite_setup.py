import pytest
import requests

VITE_URL = "http://localhost:5173"
import pytest
import requests

VITE_URL = "http://localhost:5173"
FLASK_URL = "http://localhost:5001"

VITE_ROUTES = [
    "/video-to-gif",
    "/gif-maker",
    "/crop",
    "/optimize",
    "/add-text",
]

SEO_PAGES = [
    "/convert/mp4-to-gif",
    "/convert/youtube-to-gif",
    "/features/reverse-gif",
    "/optimize/gif-under-5mb",
    "/tools/add-text-to-gif",
]

SEO_FILES = [
    ("/sitemap.xml", "sitemap"),
    ("/robots.txt", "robots.txt"),
]


def _get(base: str, path: str):
    try:
        return requests.get(f"{base}{path}", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"{base} unavailable: {exc}")


@pytest.mark.parametrize("route", VITE_ROUTES)
def test_vite_routes(route):
    response = _get(VITE_URL, route)
    assert response.status_code == 200, f"{route} returned {response.status_code}"
    content = response.text.lower()
    assert "react" in content or "root" in content, f"{route} missing React placeholder"


@pytest.mark.parametrize("page", SEO_PAGES)
def test_flask_seo_pages(page):
    response = _get(FLASK_URL, page)
    assert response.status_code == 200, f"{page} returned {response.status_code}"
    content = response.text
    assert "schema.org" in content, f"{page} missing schema markup"
    assert "og:title" in content, f"{page} missing Open Graph"
    assert "twitter:card" in content, f"{page} missing Twitter card"
    assert "canonical" in content, f"{page} missing canonical URL"


def test_flask_api_health():
    response = _get(FLASK_URL, "/api/health")
    assert response.status_code == 200, f"/api/health returned {response.status_code}"


@pytest.mark.parametrize("path,name", SEO_FILES)
def test_seo_files(path, name):
    response = _get(FLASK_URL, path)
    assert response.status_code == 200, f"{name} returned {response.status_code}"
