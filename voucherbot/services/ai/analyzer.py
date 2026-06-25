"""
AI Analyzer service — provider-agnostic structured extraction.

Architecture
------------
The public function ``analyze_post`` accepts raw post text and returns a
canonical ``ExtractedEvent`` (defined in ``voucherbot.services.ai.schema``).

Internally, two provider adapters are used in priority order:
  1. Groq  (primary)
  2. Gemini (fallback)

Each adapter is responsible for converting its raw provider response into an
``ExtractedEvent``.  The pipeline NEVER depends on which provider responded.

Retry logic on 429 rate-limit errors is preserved from the original
implementation.
"""
from __future__ import annotations

import asyncio
import json
import re
import structlog

from voucherbot.config.settings import settings
from voucherbot.services.ai.schema import ExtractedEvent

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a structured data extractor for a certification voucher aggregator.\n"
    "Analyse the post below and decide whether it is ACTUALLY offering, sharing, or "
    "announcing a free voucher, coupon, promo code, discount, or free exam for an "
    "IT/cloud certification — NOT merely discussing the concept in passing.\n\n"
    "Respond with ONLY a valid JSON object matching this exact schema (all fields "
    "optional except is_voucher and confidence):\n"
    "{\n"
    '  "is_voucher": true | false,\n'
    '  "confidence": 0.0–1.0,\n'
    '  "reason": "one-sentence explanation",\n'
    '  "vendor": "e.g. Microsoft | AWS | Google | Cisco | CompTIA | null",\n'
    '  "promotion_name": "e.g. AI Skills Fest | null",\n'
    '  "promotion_type": "voucher | discount | free_exam | bundle | beta_invite | null",\n'
    '  "certifications": ["AZ-900", "SC-300"] or null,\n'
    '  "voucher_code": "CODE or null",\n'
    '  "discount": "50% or $100 or null",\n'
    '  "registration_url": "https://... or null",\n'
    '  "start_date": "YYYY-MM-DD or null",\n'
    '  "end_date": "YYYY-MM-DD or null",\n'
    '  "regions": ["US", "Global"] or null\n'
    "}\n"
    "No markdown fences, no extra text — ONLY the JSON object.\n\n"
)

# ---------------------------------------------------------------------------
# Retry config
# ---------------------------------------------------------------------------
_MAX_RETRIES = 3
_FALLBACK_WAIT_S = 65


def _parse_retry_delay(error_str: str) -> float:
    match = re.search(r"retryDelay['\"]:\s*['\"](\\d+(?:\\.\\d+)?)s['\"]", error_str)
    if match:
        return min(float(match.group(1)) + 2, 70)
    return _FALLBACK_WAIT_S


# ---------------------------------------------------------------------------
# Shared response parser
# ---------------------------------------------------------------------------
def _parse_to_extracted_event(raw_text: str) -> ExtractedEvent | None:
    """Parse a raw provider response string into an ``ExtractedEvent``.

    Handles accidental markdown fences that some models emit despite
    instructions.  Returns ``None`` only on catastrophic parse failures.
    """
    try:
        text = raw_text.strip()
        if text.startswith("```"):
            # Strip ```json ... ``` fences
            text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        data: dict = json.loads(text)
        event = ExtractedEvent.model_validate(data)
        logger.debug(
            "ai.analyzer: extraction complete",
            is_voucher=event.is_voucher,
            confidence=event.confidence,
            vendor=event.vendor,
        )
        return event
    except Exception as exc:
        logger.warning(
            "ai.analyzer: failed to parse response",
            error=str(exc),
            raw=raw_text[:300],
        )
        # Return a safe default rather than None so callers can always proceed.
        return ExtractedEvent(is_voucher=False, confidence=0.0, reason="parse_error")


# ---------------------------------------------------------------------------
# Provider adapters
# ---------------------------------------------------------------------------
async def _call_groq(title: str, content: str | None) -> ExtractedEvent | None:
    """Groq provider adapter.  Returns None on non-retryable failure."""
    from groq import AsyncGroq  # lazy import

    client = AsyncGroq(api_key=settings.groq_api_key)
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Title: {title}\n\nContent: {content or '(no content)'}"},
    ]

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            resp = await client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                temperature=1,
                max_completion_tokens=2048,
                top_p=1,
                reasoning_effort="medium",
            )
            raw_text: str = resp.choices[0].message.content.strip()
            return _parse_to_extracted_event(raw_text)
        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str and attempt < _MAX_RETRIES:
                wait = _parse_retry_delay(error_str)
                logger.warning(
                    "ai.analyzer: Groq rate-limited, retrying",
                    attempt=attempt,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.warning(
                    "ai.analyzer: Groq failed, will try fallback",
                    error=error_str[:120],
                )
                return None
    return None


async def _call_gemini(title: str, content: str | None) -> ExtractedEvent | None:
    """Gemini provider adapter.  Returns None on non-retryable failure."""
    from google import genai  # lazy import

    client = genai.Client(api_key=settings.gemini_api_key)
    full_prompt = _SYSTEM_PROMPT + f"Title: {title}\n\nContent: {content or '(no content)'}"

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            def _call() -> str:
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=full_prompt,
                )
                return resp.text

            raw_text = (await asyncio.to_thread(_call)).strip()
            return _parse_to_extracted_event(raw_text)
        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str and attempt < _MAX_RETRIES:
                wait = _parse_retry_delay(error_str)
                logger.warning(
                    "ai.analyzer: Gemini rate-limited, retrying",
                    attempt=attempt,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)
            else:
                logger.error(
                    "ai.analyzer: Gemini unexpected error",
                    error=error_str[:200],
                )
                return None
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
async def analyze_post(title: str, content: str | None) -> ExtractedEvent | None:
    """Extract structured promotion data from post text.

    Returns an ``ExtractedEvent`` (is_voucher may be False for non-promo
    content), or ``None`` if no LLM provider is configured / all fail.

    Provider priority: Groq → Gemini.
    """
    if settings.groq_api_key:
        result = await _call_groq(title, content)
        if result is not None:
            return result

    if settings.gemini_api_key:
        result = await _call_gemini(title, content)
        if result is not None:
            return result

    if not settings.groq_api_key and not settings.gemini_api_key:
        logger.warning("ai.analyzer: no API keys configured — skipping AI extraction.")
    else:
        logger.error("ai.analyzer: all configured providers failed.")

    return None
