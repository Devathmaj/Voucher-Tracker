"""
AI Analyzer service using Google Gemini.

Receives high-probability post content (score >= SCORE_THRESHOLD) and asks
Gemini to determine whether the post is genuinely offering a free voucher /
coupon / promo code — not just mentioning the concept in passing.

Returns a structured dict saved into Post.ai_result.
"""
import asyncio
import json
import re
import structlog
from google import genai

from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)

# Module-level flag: False if the API key is missing so callers can skip gracefully.
_initialized = False

_SYSTEM_PROMPT_PREFIX = (
    "You are a content classifier for a voucher-detection system.\n"
    "Decide whether the post below is ACTUALLY offering, sharing, or announcing "
    "a free voucher, coupon, promo code, or discount code - not merely discussing "
    "vouchers in a general or historical context.\n"
    "Respond with ONLY a valid JSON object. No markdown fences, no extra text.\n"
    'Schema: {"is_voucher": true|false, "confidence": 0.0-1.0, '
    '"reason": "one-sentence explanation", "voucher_code": "extracted code or null"}\n\n'
)


_client: genai.Client | None = None


def _init_client() -> None:
    """Instantiate the Gemini client once at import time if the key is available."""
    global _initialized, _client
    if not settings.gemini_api_key:
        logger.warning("ai.analyzer: GEMINI_API_KEY not set - AI analysis will be skipped.")
        return
    _client = genai.Client(api_key=settings.gemini_api_key)
    _initialized = True
    logger.info("ai.analyzer: Gemini client initialized.")


_init_client()



# Maximum number of retries on 429 rate-limit errors
_MAX_RETRIES = 3
# Fallback wait time if the retry delay can't be parsed from the error
_FALLBACK_WAIT_S = 65


def _parse_retry_delay(error_str: str) -> float:
    """Extract the retryDelay seconds from a 429 error string."""
    match = re.search(r"retryDelay['\"]:\s*['\"](\d+(?:\.\d+)?)s['\"]", error_str)
    if match:
        return min(float(match.group(1)) + 2, 70)  # add 2s buffer, cap at 70s
    return _FALLBACK_WAIT_S


async def analyze_post(title: str, content: str | None) -> dict | None:
    """
    Send post text to Gemini and parse a structured voucher-detection result.

    Automatically retries up to _MAX_RETRIES times on 429 rate-limit errors,
    honouring the retryDelay the API provides.

    Returns a dict with keys: is_voucher, confidence, reason, voucher_code.
    Returns None if the API key is absent or a non-retryable error occurs.
    """
    if not _initialized:
        return None

    # Prepend system instructions directly into the user message so they
    # work across all API versions without needing system_instruction config.
    full_prompt = (
        _SYSTEM_PROMPT_PREFIX
        + f"Title: {title}\n\nContent: {content or '(no content)'}"
    )

    raw_text = ""

    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            # Use the synchronous API inside a thread to avoid blocking the event
            # loop. The async (aio) path depends on aiohttp which has a version
            # mismatch in this environment.
            def _call() -> str:
                resp = _client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=full_prompt,
                )
                return resp.text

            raw_text = await asyncio.to_thread(_call)
            raw_text = raw_text.strip()
            break  # success — exit retry loop

        except Exception as exc:
            error_str = str(exc)
            if "429" in error_str and attempt < _MAX_RETRIES:
                wait = _parse_retry_delay(error_str)
                logger.warning(
                    "ai.analyzer: rate-limited, retrying",
                    attempt=attempt,
                    wait_seconds=wait,
                )
                await asyncio.sleep(wait)
                continue
            elif "429" in error_str:
                logger.error("ai.analyzer: rate-limit retries exhausted", error=error_str[:120])
                return None
            else:
                logger.error("ai.analyzer: unexpected error", error=error_str[:200])
                return None

    try:
        # Strip accidental markdown fences if the model forgets our instruction
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]

        result: dict = json.loads(raw_text)
        logger.debug(
            "ai.analyzer: analysis complete",
            is_voucher=result.get("is_voucher"),
            confidence=result.get("confidence"),
        )
        return result

    except json.JSONDecodeError as exc:
        logger.warning("ai.analyzer: failed to parse JSON response", error=str(exc), raw=raw_text[:200])
        return {"is_voucher": False, "confidence": 0.0, "reason": "parse_error", "voucher_code": None}
    except Exception as exc:
        logger.error("ai.analyzer: unexpected error", error=str(exc))
        return None
