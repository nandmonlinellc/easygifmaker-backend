import pytest
import requests

BASE_URL = "https://easygifmaker-api.fly.dev"

def _request(method: str, path: str, **kwargs):
    url = f"{BASE_URL}{path}"
    try:
        return requests.request(method, url, timeout=10, **kwargs)
    except requests.RequestException as exc:
        pytest.skip(f"AI API unavailable: {exc}")


def test_ai_health():
    response = _request("get", "/api/ai/health")
    assert response.status_code == 200, f"Health endpoint returned {response.status_code}"
    assert response.json(), "Health endpoint returned empty body"


def test_ai_capabilities():
    response = _request("get", "/api/ai/capabilities")
    assert response.status_code == 200, f"Capabilities endpoint returned {response.status_code}"
    data = response.json()
    assert "service" in data, "Capabilities response missing 'service'"
    assert "endpoints" in data, "Capabilities response missing 'endpoints'"


@pytest.mark.parametrize(
    "endpoint",
    [
        "/api/ai/convert",
        "/api/ai/create-gif",
        "/api/ai/optimize",
        "/api/ai/add-text",
    ],
)
def test_ai_post_endpoints_require_input(endpoint):
    response = _request("post", endpoint, json={})
    assert response.status_code == 400, f"{endpoint} returned {response.status_code}"
    data = response.json()
    assert "usage" in data, f"{endpoint} response missing usage information"
