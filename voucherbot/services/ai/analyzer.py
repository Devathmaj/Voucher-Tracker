"""
AI Analyzer service using Google Gemini.

Receives high-probability post content (score >= SCORE_THRESHOLD) and asks
Gemini to determine whether the post is genuinely offering a free voucher /
coupon / promo code — not just mentioning the concept in passing.

Returns a structured dict saved into Post.ai_result.
"""
import json
import structlog
import google.generativeai as genai

from voucherbot.config.settings import settings

logger = structlog.get_logger(__name__)

# Module-level flag: False if the API key is missing so callers can skip gracefully.
_initialized = False

_SYSTEM_PROMPT = """You are a content classifier for a voucher-detection system.
Your task is to decide whether a given post is ACTUALLY offering, sharing, or
announcing a free voucher, coupon, promo code, or discount code — as opposed to
merely discussing vouchers in a general or historical context.

Respond with ONLY a valid JSON object. No markdown fences, no extra text.
Schema:
{
  "is_voucher": true | false,
  "confidence": 0.0 – 1.0,
  "reason": "one-sentence explanation",
  "voucher_code": "extracted code string or null"
}
"""


def _init_client() -> None:
    """Configure the Gemini SDK once at import time if the key is available."""
    global _initialized
    if not settings.gemini_api_key:
        logger.warning("ai.analyzer: GEMINI_API_KEY not set — AI analysis will be skipped.")
        return
    genai.configure(api_key=settings.gemini_api_key)
    _initialized = True
    logger.info("ai.analyzer: Gemini client initialized.")


_init_client()


async def analyze_post(title: str, content: str | None) -> dict | None:
    """
    Send post text to Gemini and parse a structured voucher-detection result.

    Returns a dict with keys: is_voucher, confidence, reason, voucher_code.
    Returns None if the API key is absent or a non-retryable error occurs.
    """
    if not _initialized:
        return None

    text_body = f"Title: {title}\n\nContent: {content or '(no content)'}"

    try:
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            system_instruction=_SYSTEM_PROMPT,
        )

        # The Python SDK's generate_content is synchronous; run it in a thread
        # so it doesn't block the event loop.
        import asyncio
        response = await asyncio.to_thread(
            model.generate_content,
            text_body,
        )

        raw_text: str = response.text.strip()

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
        logger.warning("ai.analyzer: failed to parse JSON response", error=str(exc), raw=response.text[:200])
        return {"is_voucher": False, "confidence": 0.0, "reason": "parse_error", "voucher_code": None}
    except Exception as exc:
        logger.error("ai.analyzer: unexpected error", error=str(exc))
        return None
