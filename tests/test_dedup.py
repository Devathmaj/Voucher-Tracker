"""
Tests for Stage 1 document deduplication utilities.

Covers:
  - normalise_url: tracking param stripping, scheme normalisation,
    trailing slash removal, fragment stripping.
  - content_hash: stability, determinism, case insensitivity.
  - deduplicate_batch: intra-batch duplicate removal.
"""
from __future__ import annotations

import pytest
from urllib.parse import urlparse

from voucherbot.providers.base import NormalizedPost
from voucherbot.services.ingestion.dedup import (
    content_hash,
    deduplicate_batch,
    identity_hash,
    normalise_url,
)


# ---------------------------------------------------------------------------
# normalise_url
# ---------------------------------------------------------------------------

class TestNormaliseUrl:
    def test_strips_utm_params(self):
        url = "https://example.com/promo?utm_source=newsletter&utm_medium=email"
        assert normalise_url(url) == "https://example.com/promo"

    def test_strips_fbclid(self):
        url = "https://example.com/page?fbclid=abc123&keep=yes"
        result = normalise_url(url)
        assert "fbclid" not in result
        assert "keep=yes" in result

    def test_strips_fragment(self):
        url = "https://example.com/post#section-2"
        assert "#" not in normalise_url(url)

    def test_normalises_http_to_https(self):
        url = "http://example.com/page"
        assert normalise_url(url).startswith("https://")

    def test_removes_trailing_slash(self):
        url = "https://example.com/page/"
        assert not normalise_url(url).endswith("/")

    def test_lowercases_host(self):
        url = "https://Example.COM/page"
        assert urlparse(normalise_url(url)).hostname == "example.com"

    def test_preserves_non_tracking_params(self):
        url = "https://example.com/search?q=az900&page=2"
        result = normalise_url(url)
        assert "q=az900" in result
        assert "page=2" in result

    def test_empty_url_returns_empty(self):
        assert normalise_url("") == ""

    def test_same_url_different_utm_values_normalise_equal(self):
        a = "https://blog.ms.com/post?utm_campaign=x"
        b = "https://blog.ms.com/post?utm_campaign=y"
        assert normalise_url(a) == normalise_url(b)


# ---------------------------------------------------------------------------
# content_hash
# ---------------------------------------------------------------------------

class TestContentHash:
    def test_is_40_chars(self):
        h = content_hash("Test Title", "https://example.com")
        assert len(h) == 40

    def test_is_deterministic(self):
        h1 = content_hash("Azure 50% Off", "https://azure.com/promo")
        h2 = content_hash("Azure 50% Off", "https://azure.com/promo")
        assert h1 == h2

    def test_case_insensitive_title(self):
        h1 = content_hash("Azure Promo", "https://azure.com/promo")
        h2 = content_hash("AZURE PROMO", "https://azure.com/promo")
        assert h1 == h2

    def test_strips_utm_from_url_before_hashing(self):
        h1 = identity_hash("https://example.com/p")
        h2 = identity_hash("https://example.com/p?utm_source=reddit")
        assert h1 == h2

    def test_different_titles_produce_different_hashes(self):
        h1 = content_hash("AWS Promo", "https://aws.com")
        h2 = content_hash("Azure Promo", "https://aws.com")
        assert h1 != h2

    def test_different_urls_produce_different_hashes(self):
        h1 = content_hash("Same Title", "https://site-a.com/post")
        h2 = content_hash("Same Title", "https://site-b.com/post")
        assert h1 != h2


# ---------------------------------------------------------------------------
# deduplicate_batch
# ---------------------------------------------------------------------------

def _make_post(title: str, url: str, external_id: str = "x") -> NormalizedPost:
    return NormalizedPost(external_id=external_id, url=url, title=title)


class TestDeduplicateBatch:
    def test_removes_exact_duplicates(self):
        posts = [
            _make_post("Azure Promo", "https://azure.com/promo", "a"),
            _make_post("Azure Promo", "https://azure.com/promo", "b"),
        ]
        result = deduplicate_batch(posts)
        assert len(result) == 1
        assert result[0].external_id == "a"  # first occurrence kept

    def test_removes_utm_duplicates(self):
        posts = [
            _make_post("Azure Promo", "https://azure.com/promo", "a"),
            _make_post("Azure Promo", "https://azure.com/promo?utm_source=twitter", "b"),
        ]
        result = deduplicate_batch(posts)
        assert len(result) == 1

    def test_keeps_unique_posts(self):
        posts = [
            _make_post("AWS Promo", "https://aws.com/promo", "a"),
            _make_post("Azure Promo", "https://azure.com/promo", "b"),
            _make_post("GCP Promo", "https://gcp.com/promo", "c"),
        ]
        result = deduplicate_batch(posts)
        assert len(result) == 3

    def test_empty_input_returns_empty(self):
        assert deduplicate_batch([]) == []

    def test_single_post_returns_itself(self):
        post = _make_post("Title", "https://example.com/page")
        assert deduplicate_batch([post]) == [post]

    def test_preserves_order(self):
        posts = [
            _make_post("A", "https://a.com", "1"),
            _make_post("B", "https://b.com", "2"),
            _make_post("C", "https://c.com", "3"),
        ]
        result = deduplicate_batch(posts)
        assert [p.external_id for p in result] == ["1", "2", "3"]
