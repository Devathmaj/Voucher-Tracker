"""
Stage 1 — Deterministic document deduplication.

Public API
----------
normalise_url(url)                    -> str
identity_hash(url)                    -> str   (SHA-256 hex, stable page identity)
content_hash(title, content, date)    -> str   (SHA-256 hex, changes when content changes)
deduplicate_batch(posts)              -> list[NormalizedPost]
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime
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


def identity_hash(url: str) -> str:
    """SHA-256 of the normalised URL — stable identity regardless of content changes."""
    return hashlib.sha256(normalise_url(url).encode("utf-8")).hexdigest()


def content_hash(
    title: str,
    content: str | None = None,
    published_at: datetime | None = None,
) -> str:
    """SHA-256 of normalised title + content + date — changes when the page changes."""
    norm_title = re.sub(r"\s+", " ", title.strip().lower())
    norm_content = re.sub(r"\s+", " ", (content or "").strip().lower())
    norm_date = published_at.isoformat() if published_at else ""
    key = f"{norm_title}|{norm_content}|{norm_date}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:40]


def deduplicate_batch(posts: Sequence[NormalizedPost]) -> list[NormalizedPost]:
    """Remove intra-batch duplicates by identity_hash, keeping the first occurrence."""
    seen: set[str] = set()
    unique: list[NormalizedPost] = []
    for post in posts:
        h = identity_hash(post.url)
        if h not in seen:
            seen.add(h)
            unique.append(post)
    return unique
