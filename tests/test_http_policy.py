"""Tests for robots.txt / politeness helpers."""

from __future__ import annotations

from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from voucherbot.providers.http_policy import (
    RobotsDisallowedError,
    clear_policy_caches,
    is_allowed,
    polite_get,
)


@pytest.fixture(autouse=True)
def _reset(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    clear_policy_caches()
    monkeypatch.setattr(
        "voucherbot.providers.http_policy.settings.scraper_respect_robots",
        True,
    )
    monkeypatch.setattr(
        "voucherbot.providers.http_policy.settings.scraper_min_delay_seconds",
        0.0,
    )
    monkeypatch.setattr(
        "voucherbot.providers.http_policy.settings.scraper_user_agent",
        "VoucherBotTest/0.1",
    )
    yield
    clear_policy_caches()


def _robots_response(body: str) -> httpx.Response:
    request = httpx.Request("GET", "https://example.com/robots.txt")
    return httpx.Response(200, request=request, text=body)


@pytest.mark.asyncio
async def test_is_allowed_respects_disallow() -> None:
    robots = "User-agent: *\nDisallow: /private\n"

    with patch("httpx.AsyncClient") as mock_cls:
        client = mock_cls.return_value
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=_robots_response(robots))

        assert await is_allowed("https://example.com/public") is True
        assert await is_allowed("https://example.com/private/page") is False


@pytest.mark.asyncio
async def test_polite_get_raises_when_disallowed() -> None:
    robots = "User-agent: *\nDisallow: /\n"

    with patch("httpx.AsyncClient") as mock_cls:
        client = mock_cls.return_value
        client.__aenter__ = AsyncMock(return_value=client)
        client.__aexit__ = AsyncMock(return_value=None)
        client.get = AsyncMock(return_value=_robots_response(robots))

        with pytest.raises(RobotsDisallowedError):
            await polite_get("https://blocked.example/page")
