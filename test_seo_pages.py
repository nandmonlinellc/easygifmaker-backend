import pytest
import requests

BASE_URL = "http://localhost:5001"
TEST_PAGES = [
    "/convert/mp4-to-gif",
    "/convert/youtube-to-gif",
    "/features/reverse-gif",
    "/optimize/gif-under-5mb",
    "/tools/add-text-to-gif",
]

def _get(path: str):
    try:
        return requests.get(f"{BASE_URL}{path}", timeout=5)
    except requests.RequestException as exc:
        pytest.skip(f"Local server unavailable: {exc}")


@pytest.mark.parametrize("page", TEST_PAGES)
def test_seo_page_status_and_meta(page):
    response = _get(page)
    assert response.status_code == 200, f"{page} returned {response.status_code}"
    content = response.text
    assert "schema.org" in content, f"{page} missing schema markup"
    assert "og:title" in content, f"{page} missing Open Graph tags"


def test_sitemap_contains_pages():
    response = _get("/sitemap.xml")
    assert response.status_code == 200, f"Sitemap returned {response.status_code}"
    for page in TEST_PAGES:
        slug = page.strip("/")
        assert slug in response.text, f"Sitemap missing {page}"


def test_robots_txt_has_sitemap():
    response = _get("/robots.txt")
    assert response.status_code == 200, f"Robots.txt returned {response.status_code}"
    assert "sitemap" in response.text.lower(), "Robots.txt missing sitemap reference"
