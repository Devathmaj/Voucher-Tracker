"""
Stage 1 — Deterministic document deduplication.

This module is purely functional (no I/O, no DB) so it is easy to unit-test
and reason about.

Public API
----------
normalise_url(url)           -> str
content_hash(title, url)     -> str   (SHA-1 hex, 40 chars)
deduplicate_batch(posts)     -> list[NormalizedPost]
"""
from __future__ import annotations

import hashlib
import re
from typing import Sequence
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from voucherbot.providers.base import NormalizedPost

# Query parameters that carry no semantic meaning and should be stripped.
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        # UTM family
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "utm_id", "utm_reader", "utm_name",
        # Referral / tracking
        "ref", "referrer", "ref_src", "ref_url",
        "fbclid", "gclid", "gad_source", "msclkid", "twclid",
        "ocid", "cid", "icid",
        # Reddit / social
        "share_id",
        # Microsoft / Bing
        "WT.mc_id",
    }
)


def normalise_url(url: str) -> str:
    """Return a canonical form of *url* for deduplication purposes.

    Steps applied (in order):
    1. Strip leading/trailing whitespace.
    2. Force scheme to ``https`` (``http`` and ``https`` are treated as equal).
    3. Remove trailing slash from the path.
    4. Remove fragment identifiers (``#section``).
    5. Drop all query parameters whose names are in ``_TRACKING_PARAMS``.
    6. Lower-case the host name.

    The result is NOT necessarily a valid URL to visit — it is used solely as
    a stable key for deduplication hashing.
    """
    url = url.strip()
    if not url:
        return url

    parsed = urlparse(url)

    scheme = "https"
    netloc = parsed.netloc.lower()
    path = parsed.path.rstrip("/")
    fragment = ""  # always stripped

    # Filter tracking params; preserve order of remaining params.
    kept_params = [
        (k, v)
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in {p.lower() for p in _TRACKING_PARAMS}
    ]
    query = urlencode(kept_params)

    return urlunparse((scheme, netloc, path, parsed.params, query, fragment))


def content_hash(title: str, url: str) -> str:
    """Return a 40-char SHA-1 hex of ``normalised(title) | normalised(url)``.

    The pipe character acts as a separator so that a title suffix cannot
    accidentally collide with a URL prefix.
    """
    norm_title = re.sub(r"\s+", " ", title.strip().lower())
    norm_url = normalise_url(url)
    key = f"{norm_title}|{norm_url}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def deduplicate_batch(posts: Sequence[NormalizedPost]) -> list[NormalizedPost]:
    """Remove intra-batch duplicates, keeping the first occurrence of each hash.

    This catches the case where two configured sources point to the same
    underlying feed / page and fetch the same articles in one pipeline run.
    Cross-source duplicates from *previous* runs are handled at DB level by
    the partial unique index on ``posts.content_hash``.

    The returned list preserves the original ordering of unique posts.
    """
    seen: set[str] = set()
    unique: list[NormalizedPost] = []
    for post in posts:
        h = content_hash(post.title, post.url)
        if h not in seen:
            seen.add(h)
            unique.append(post)
    return unique
