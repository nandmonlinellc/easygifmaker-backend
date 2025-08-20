import pytest
import requests

BASE_URL = "http://localhost:5001"
import pytest
import requests

BASE_URL = "http://localhost:5001"
SEO_PAGES = [
    "/convert/mp4-to-gif",
    "/convert/youtube-to-gif",
    "/convert/avi-to-gif",
    "/features/reverse-gif",
    "/features/crop-gif",
    "/features/resize-gif",
    "/optimize/gif-under-5mb",
    "/optimize/optimize-gif-for-web",
    "/tools/add-text-to-gif",
    "/tools/gif-speed-control",
]
REACT_ROUTES = [
    "/video-to-gif",
    "/gif-maker",
    "/crop",
    "/optimize",
    "/add-text",
]

def _get(path: str):
    try:
        return requests.get(f"{BASE_URL}{path}", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"Local server unavailable: {exc}")


@pytest.mark.parametrize("page", SEO_PAGES)
def test_seo_pages_have_meta(page):
    response = _get(page)
    assert response.status_code == 200, f"{page} returned {response.status_code}"
    content = response.text
    assert "schema.org" in content, f"{page} missing schema markup"
    assert "og:title" in content, f"{page} missing Open Graph"
    assert "twitter:card" in content, f"{page} missing Twitter card"
    assert "canonical" in content, f"{page} missing canonical URL"
    assert "faq" in content.lower(), f"{page} missing FAQ content"


def test_sitemap_lists_key_pages():
    response = _get("/sitemap.xml")
    assert response.status_code == 200, f"Sitemap returned {response.status_code}"
    for page in ["/convert/mp4-to-gif", "/video-to-gif"]:
        assert page.strip("/") in response.text, f"Sitemap missing {page}"


def test_robots_txt_references_sitemap():
    response = _get("/robots.txt")
    assert response.status_code == 200, f"robots.txt returned {response.status_code}"
    text = response.text.lower()
    assert "sitemap" in text, "robots.txt missing sitemap reference"
    assert "convert/" in text, "robots.txt missing convert directory"


@pytest.mark.parametrize("route", REACT_ROUTES)
def test_react_routes(route):
    response = _get(route)
    assert response.status_code == 200, f"{route} returned {response.status_code}"
    content = response.text.lower()
    assert "react" in content or "root" in content, f"{route} not serving React app"


def test_api_health_endpoint():
    response = _get("/api/health")
    assert response.status_code == 200, f"/api/health returned {response.status_code}"
