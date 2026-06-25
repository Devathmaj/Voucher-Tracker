"""
Canonical AI extraction schema.

Every LLM provider adapter (Groq, Gemini, future providers) is responsible for
converting its raw response into an ``ExtractedEvent``.  The rest of the
ingestion pipeline only ever sees this type — never a provider-specific dict.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, field_validator


class ExtractedEvent(BaseModel):
    """Structured representation of a certification promotion extracted by AI.

    Fields are intentionally nullable so a provider can return a partial result
    when the source content is sparse.  The EventMatcher will only score fields
    that are non-null.
    """

    # Is this content even voucher/promo related?
    is_voucher: bool = False
    confidence: float = 0.0  # 0.0 – 1.0, AI's own confidence in is_voucher

    # --- Extracted promotion fields ---
    vendor: Optional[str] = None
    promotion_name: Optional[str] = None
    promotion_type: Optional[str] = None       # e.g. "voucher", "discount", "free_exam"
    certifications: Optional[list[str]] = None  # e.g. ["AZ-104", "SC-300"]
    voucher_code: Optional[str] = None
    discount: Optional[str] = None             # e.g. "50%" or "$100"
    registration_url: Optional[str] = None
    start_date: Optional[str] = None           # ISO 8601 date string or None
    end_date: Optional[str] = None             # ISO 8601 date string or None
    regions: Optional[list[str]] = None        # e.g. ["US", "Global"]

    # Human-readable reason from the AI (for debugging / audit)
    reason: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))

    @field_validator("voucher_code", mode="before")
    @classmethod
    def normalise_voucher_code(cls, v: object) -> Optional[str]:
        """Upper-case and strip voucher codes for consistent matching."""
        if v is None or not isinstance(v, str):
            return None
        code = v.strip().upper()
        return code or None

    @field_validator("vendor", mode="before")
    @classmethod
    def normalise_vendor(cls, v: object) -> Optional[str]:
        if v is None or not isinstance(v, str):
            return None
        return v.strip().lower() or None
