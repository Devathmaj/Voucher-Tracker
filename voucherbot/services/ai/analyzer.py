"""
AI Analyzer service.

Receives high-probability post content (score >= SCORE_THRESHOLD) and asks
Groq (primary) or Gemini (fallback) to determine whether the post is genuinely 
offering a free voucher / coupon / promo code — not just mentioning the concept 
in passing.

Returns a structured dict saved into Post.ai_result.
"""
import asyncio
import json
import re
import structlog
from google import genai
from groq import AsyncGroq

from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)

# Module-level flag: False if no API keys are available so callers can skip gracefully.
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


_groq_client: AsyncGroq | None = None
_gemini_client: genai.Client | None = None


def _init_client() -> None:
    """Instantiate the AI clients once at import time if their keys are available."""
    global _initialized, _groq_client, _gemini_client
    
    if settings.groq_api_key:
        _groq_client = AsyncGroq(api_key=settings.groq_api_key)
        logger.info("ai.analyzer: Groq client initialized.")
    else:
        logger.warning("ai.analyzer: GROQ_API_KEY not set - Groq will be skipped.")

    if settings.gemini_api_key:
        _gemini_client = genai.Client(api_key=settings.gemini_api_key)
        logger.info("ai.analyzer: Gemini client initialized.")
    else:
        logger.warning("ai.analyzer: GEMINI_API_KEY not set - Gemini fallback will be skipped.")
        
    _initialized = _groq_client is not None or _gemini_client is not None


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


def _parse_response(raw_text: str) -> dict | None:
    """Helper to parse the raw text output into the structured dictionary."""
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
        logger.error("ai.analyzer: unexpected error in parsing", error=str(exc))
        return None


async def analyze_post(title: str, content: str | None) -> dict | None:
    """
    Send post text to Groq (primary) or Gemini (fallback) and parse a structured voucher-detection result.

    Automatically retries up to _MAX_RETRIES times on 429 rate-limit errors.

    Returns a dict with keys: is_voucher, confidence, reason, voucher_code.
    Returns None if no API keys are absent or non-retryable errors occur on all models.
    """
    if not _initialized:
        return None

    # 1. Try Groq first if available
    if _groq_client:
        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT_PREFIX},
            {"role": "user", "content": f"Title: {title}\n\nContent: {content or '(no content)'}"}
        ]

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                resp = await _groq_client.chat.completions.create(
                    model="openai/gpt-oss-120b",
                    messages=messages,
                    temperature=1,
                    max_completion_tokens=2048,
                    top_p=1,
                    reasoning_effort="medium"
                )
                raw_text = resp.choices[0].message.content.strip()
                return _parse_response(raw_text)

            except Exception as exc:
                error_str = str(exc)
                if "429" in error_str and attempt < _MAX_RETRIES:
                    wait = _parse_retry_delay(error_str)
                    logger.warning("ai.analyzer: Groq rate-limited, retrying", attempt=attempt, wait_seconds=wait)
                    await asyncio.sleep(wait)
                    continue
                else:
                    logger.warning("ai.analyzer: Groq failed or exhausted retries. Falling back to Gemini if available.", error=error_str[:120])
                    break  # Exit Groq loop and try fallback

    # 2. Try Gemini as fallback if available
    if _gemini_client:
        full_prompt = (
            _SYSTEM_PROMPT_PREFIX
            + f"Title: {title}\n\nContent: {content or '(no content)'}"
        )

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                # Use the synchronous API inside a thread to avoid blocking the event loop
                def _call() -> str:
                    resp = _gemini_client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=full_prompt,
                    )
                    return resp.text

                raw_text = await asyncio.to_thread(_call)
                raw_text = raw_text.strip()
                return _parse_response(raw_text)

            except Exception as exc:
                error_str = str(exc)
                if "429" in error_str and attempt < _MAX_RETRIES:
                    wait = _parse_retry_delay(error_str)
                    logger.warning("ai.analyzer: Gemini rate-limited, retrying", attempt=attempt, wait_seconds=wait)
                    await asyncio.sleep(wait)
                    continue
                else:
                    logger.error("ai.analyzer: Gemini unexpected error", error=error_str[:200])
                    return None

    logger.error("ai.analyzer: All configured AI services failed.")
    return None
