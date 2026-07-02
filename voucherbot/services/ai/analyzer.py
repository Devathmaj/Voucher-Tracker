"""
AI Analyzer service — provider-agnostic structured extraction.

Architecture
------------
The public function ``analyze_post`` accepts raw post text and returns a
canonical ``ExtractedEvent`` (defined in ``voucherbot.services.ai.schema``).

Internally, providers are tried in priority order:
  1. Groq / llama-3.1-8b-instant  (primary)
  2. Groq / openai/gpt-oss-120b   (fallback on non-429 failure)
  3. Gemini                        (final fallback on non-429 failure)

Each adapter is responsible for converting its raw provider response into an
``ExtractedEvent``.  The pipeline NEVER depends on which provider responded.

Retry logic on 429 rate-limit errors is preserved from the original
implementation.
"""
from __future__ import annotations

import asyncio
from collections import deque
import json
import re
import time
import structlog

from voucherbot.config.settings import settings
from voucherbot.services.ai.schema import ExtractedEvent

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared prompt
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = (
    "You are a structured data extractor for a certification voucher aggregator.\n"
    "Decide whether the post shows ANY intent to offer, share, announce, or point to "
    "a certification voucher, coupon, promo, discount, free exam, exam credit, or "
    "similar deal for IT/cloud certifications.\n\n"
    "Set is_voucher=true when there is promotional intent — even if incomplete. "
    "A voucher CODE is NOT required. Registration URL, dates, vendor, or exact "
    "cert name may be missing. Partial signals still count (e.g. 'free AZ-900 exam "
    "this week', '50% off CompTIA', 'voucher giveaway', 'claim your exam credit').\n"
    "Set is_voucher=false only for pure discussion, questions, or news with no "
    "actionable promo intent.\n"
    "confidence is your belief in that intent (0.0–1.0). Do NOT require high "
    "confidence or a code to set is_voucher=true — use lower confidence instead.\n\n"
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
_GROQ_PRIMARY_MODEL = "llama-3.1-8b-instant"
_GROQ_FALLBACK_MODEL = "openai/gpt-oss-120b"
_GROQ_MODEL_TPM = {
    "openai/gpt-oss-120b": 8000,
    "openai/gpt-oss-20b": 8000,
    "qwen/qwen3.6-27b": 8000,
    "llama-3.3-70b-versatile": 12000,
    "llama-3.1-8b-instant": 6000,
    "groq/compound": 70000,
    "groq/compound-mini": 70000,
}
_groq_rate_lock = asyncio.Lock()
_groq_request_times: deque[float] = deque()
_groq_token_times: deque[tuple[float, int]] = deque()
_groq_token_reservations: dict[int, tuple[float, int]] = {}  # id → (timestamp, reserved)
_groq_reservation_counter: int = 0


def _parse_retry_delay(error_str: str) -> float:
    match = re.search(r"retryDelay['\"]:\s*['\"](\\d+(?:\\.\\d+)?)s['\"]", error_str)
    if match:
        return min(float(match.group(1)) + 2, 70)
    return _FALLBACK_WAIT_S


def _groq_tokens_per_minute(model: str) -> int:
    if settings.groq_tokens_per_minute:
        return settings.groq_tokens_per_minute
    return _GROQ_MODEL_TPM.get(model, 6000)


def _estimate_tokens(text: str) -> int:
    # ~4 chars/token is realistic for English; cap completion buffer at 512.
    return max(1, len(text) // 4) + min(settings.groq_max_completion_tokens, 512)


async def _wait_for_groq_budget(estimated_tokens: int, model: str) -> int:
    """Reserve budget; returns a reservation ID to settle with actual tokens after the call."""
    global _groq_reservation_counter
    rpm = max(1, settings.groq_requests_per_minute)
    tpm = max(1, _groq_tokens_per_minute(model))
    estimated_tokens = min(estimated_tokens, tpm)

    async with _groq_rate_lock:
        while True:
            now = time.monotonic()
            cutoff = now - 60
            while _groq_request_times and _groq_request_times[0] <= cutoff:
                _groq_request_times.popleft()
            while _groq_token_times and _groq_token_times[0][0] <= cutoff:
                _groq_token_times.popleft()
            # Expire stale reservations (e.g. calls that raised before settling)
            stale = [rid for rid, (ts, _) in _groq_token_reservations.items() if now - ts > 120]
            for rid in stale:
                _groq_token_reservations.pop(rid, None)

            reserved = sum(t for _, t in _groq_token_reservations.values())
            used_tokens = sum(tokens for _, tokens in _groq_token_times) + reserved
            has_request_budget = len(_groq_request_times) < rpm
            has_token_budget = used_tokens + estimated_tokens <= tpm

            if has_request_budget and has_token_budget:
                _groq_request_times.append(now)
                _groq_reservation_counter += 1
                rid = _groq_reservation_counter
                _groq_token_reservations[rid] = (now, estimated_tokens)
                return rid

            wait_until = now + 1
            if not has_request_budget and _groq_request_times:
                wait_until = max(wait_until, _groq_request_times[0] + 60)
            if not has_token_budget and _groq_token_times:
                wait_until = max(wait_until, _groq_token_times[0][0] + 60)

            wait_seconds = max(1.0, wait_until - now)
            logger.info(
                "ai.analyzer: waiting for Groq rate budget",
                wait_seconds=round(wait_seconds, 2),
                model=model,
                rpm=rpm,
                tpm=tpm,
                estimated_tokens=estimated_tokens,
                used_tokens=used_tokens,
            )
            await asyncio.sleep(wait_seconds)


async def _settle_groq_budget(reservation_id: int, actual_tokens: int) -> None:
    """Replace the pre-flight reservation with the actual token count from the API response."""
    async with _groq_rate_lock:
        entry = _groq_token_reservations.pop(reservation_id, None)
        if entry is not None:
            _groq_token_times.append((entry[0], actual_tokens))


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
async def _call_groq_model(title: str, content: str | None, model: str) -> ExtractedEvent | None:
    """Call a specific Groq model. Returns None on non-retryable failure, raises on 429."""
    from groq import AsyncGroq  # lazy import

    client = AsyncGroq(api_key=settings.groq_api_key)
    content_for_prompt = content or "(no content)"
    if len(content_for_prompt) > settings.groq_max_input_chars:
        content_for_prompt = content_for_prompt[: settings.groq_max_input_chars]
        logger.info(
            "ai.analyzer: truncated Groq input",
            title=title[:80],
            max_input_chars=settings.groq_max_input_chars,
        )

    user_prompt = f"Title: {title}\n\nContent: {content_for_prompt}"
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    estimated_tokens = _estimate_tokens(_SYSTEM_PROMPT + user_prompt)

    for attempt in range(1, _MAX_RETRIES + 1):
        rid = await _wait_for_groq_budget(estimated_tokens, model)
        try:
            params = {
                "model": model,
                "messages": messages,
                "temperature": 1,
                "max_completion_tokens": settings.groq_max_completion_tokens,
                "top_p": 1,
            }
            if model.startswith("openai/gpt-oss-"):
                params["reasoning_effort"] = "medium"

            resp = await client.chat.completions.create(**params)
            actual = getattr(resp.usage, "total_tokens", None) or estimated_tokens
            await _settle_groq_budget(rid, actual)
            raw_text: str = resp.choices[0].message.content.strip()
            return _parse_to_extracted_event(raw_text)
        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str:
                # Discard reservation — Groq didn't consume tokens
                async with _groq_rate_lock:
                    _groq_token_reservations.pop(rid, None)
                if attempt < _MAX_RETRIES:
                    wait = _parse_retry_delay(error_str)
                    logger.warning(
                        "ai.analyzer: Groq rate-limited, retrying",
                        model=model,
                        attempt=attempt,
                        wait_seconds=wait,
                    )
                    await asyncio.sleep(wait)
                else:
                    raise  # propagate 429 so caller skips to next provider
            else:
                logger.warning(
                    "ai.analyzer: Groq model failed, will try next provider",
                    model=model,
                    error=error_str[:120],
                )
                return None
    return None


async def _call_groq(title: str, content: str | None) -> ExtractedEvent | None:
    """Groq adapter: tries primary (llama-3.1-8b-instant), falls back to gpt-oss on non-429 failure."""
    result = await _call_groq_model(title, content, _GROQ_PRIMARY_MODEL)
    if result is not None:
        return result
    # Primary returned None (non-429 failure) — try fallback model
    logger.info("ai.analyzer: Groq primary failed, trying fallback model", fallback=_GROQ_FALLBACK_MODEL)
    return await _call_groq_model(title, content, _GROQ_FALLBACK_MODEL)


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

    Provider priority: Groq/llama (primary) → Groq/gpt-oss (fallback) → Gemini (final fallback).
    Fallback is triggered only on non-429 failures; 429s are retried within each provider.
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
