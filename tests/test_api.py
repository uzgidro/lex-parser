import httpx
import respx

from tests.conftest import FULL_PAGE_HTML


LEX_SEARCH_URL = "https://lex.uz/ru/search/nat"


# ── /health ────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


# ── /search ────────────────────────────────────────────────────────────────

class TestSearch:
    def test_valid_query_page1(self, client):
        client.respx_mock.get(url__startswith=LEX_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=FULL_PAGE_HTML)
        )

        resp = client.get("/search", params={"searchtitle": "kodeks", "page": 1})
        assert resp.status_code == 200

        data = resp.json()
        assert "documents" in data
        assert "current_page" in data
        assert "total_pages" in data
        assert data["current_page"] == 1
        assert data["total_pages"] == 3
        assert len(data["documents"]) == 1
        doc = data["documents"][0]
        assert doc["title"] == "Test Document"
        assert doc["url"] == "https://lex.uz/docs/100"
        assert doc["status"] == "active"

    def test_valid_query_page2_posts_with_viewstate(self, client):
        # First GET returns the page with ASP fields
        client.respx_mock.get(url__startswith=LEX_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=FULL_PAGE_HTML)
        )
        # Second POST returns the page 2 results
        client.respx_mock.post(url__startswith=LEX_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=FULL_PAGE_HTML)
        )

        resp = client.get("/search", params={"searchtitle": "kodeks", "page": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_page"] == 2

    def test_missing_searchtitle(self, client):
        resp = client.get("/search")
        assert resp.status_code == 422

    def test_page_zero(self, client):
        resp = client.get("/search", params={"searchtitle": "test", "page": 0})
        assert resp.status_code == 422

    def test_page_101(self, client):
        resp = client.get("/search", params={"searchtitle": "test", "page": 101})
        assert resp.status_code == 422

    def test_upstream_500(self, client):
        client.respx_mock.get(url__startswith=LEX_SEARCH_URL).mock(
            return_value=httpx.Response(500)
        )

        resp = client.get("/search", params={"searchtitle": "test"})
        assert resp.status_code == 500

    def test_upstream_unreachable(self, client):
        client.respx_mock.get(url__startswith=LEX_SEARCH_URL).mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        resp = client.get("/search", params={"searchtitle": "test"})
        assert resp.status_code == 503

    def test_cache_serves_second_request(self, client):
        route = client.respx_mock.get(url__startswith=LEX_SEARCH_URL).mock(
            return_value=httpx.Response(200, text=FULL_PAGE_HTML)
        )

        # First request — hits upstream
        resp1 = client.get("/search", params={"searchtitle": "cache_test"})
        assert resp1.status_code == 200

        # Second identical request — served from cache
        resp2 = client.get("/search", params={"searchtitle": "cache_test"})
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json()

        # Only one upstream call was made
        assert route.call_count == 1
