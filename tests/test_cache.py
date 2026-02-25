from unittest.mock import patch

from main import SearchCache, SearchResponse


def _make_response(**overrides) -> SearchResponse:
    defaults = {"documents": [], "current_page": 1, "total_pages": 1}
    defaults.update(overrides)
    return SearchResponse(**defaults)


class TestSearchCache:
    def test_set_then_get(self, cache: SearchCache):
        value = _make_response()
        cache.set("key1", value)
        assert cache.get("key1") == value

    def test_get_missing_key(self, cache: SearchCache):
        assert cache.get("nonexistent") is None

    def test_get_expired_entry(self, cache: SearchCache):
        value = _make_response()
        # Insert at t=100
        with patch("main.monotonic", return_value=100.0):
            cache.set("exp", value)
        # Read at t=100+ttl+1 → expired
        with patch("main.monotonic", return_value=100.0 + cache._ttl + 1):
            assert cache.get("exp") is None

    def test_eviction_on_max_size(self, cache: SearchCache):
        # cache fixture has max_size=4
        for i in range(4):
            cache.set(f"k{i}", _make_response(current_page=i))

        # All 4 present
        for i in range(4):
            assert cache.get(f"k{i}") is not None

        # Insert 5th → oldest (k0) evicted
        cache.set("k_new", _make_response(current_page=99))
        assert cache.get("k0") is None
        assert cache.get("k_new") is not None
        assert cache.get("k_new").current_page == 99

    def test_expired_cleaned_on_access(self, cache: SearchCache):
        with patch("main.monotonic", return_value=100.0):
            cache.set("old", _make_response(current_page=1))
        with patch("main.monotonic", return_value=200.0):
            cache.set("fresh", _make_response(current_page=2))

        # Advance time so "old" is expired but "fresh" is not
        with patch("main.monotonic", return_value=100.0 + cache._ttl + 1):
            assert cache.get("old") is None
            assert cache.get("fresh") is not None
