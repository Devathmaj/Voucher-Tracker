from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class EventMatcherConfig(BaseModel):
    """Scoring weights and thresholds for canonical event matching.

    Scores are additive. A post's AI-extracted fields are compared against each
    existing candidate Event and a confidence score is computed:

      - >= auto_merge_threshold  → attach to existing Event.
      - >= possible_match_threshold (and < auto_merge_threshold)
                                 → mark as POSSIBLE_MATCH for future review.
      - < possible_match_threshold → create a new Event.
    """

    # --- Scoring weights ---
    weight_registration_url: int = 50
    weight_voucher_code: int = 40
    weight_promotion_name: int = 20
    weight_vendor: int = 15
    weight_certifications: int = 15
    weight_date_overlap: int = 10

    # --- Thresholds ---
    auto_merge_threshold: int = 75
    possible_match_threshold: int = 60

    # --- Promotion-name similarity cutoff (0–1) for partial weight credit ---
    # Below this similarity the name score contributes 0, at or above it
    # contributes the full weight_promotion_name value.
    name_similarity_threshold: float = 0.60


# Ordered from most to least authoritative. Lower index = higher priority.
# Used by the EventMatcher when merging fields from a new post into an existing
# Event (a higher-priority source's non-null value wins over a lower-priority
# source's non-null value).
SOURCE_PRIORITY: list[str] = [
    "WEBSITE",   # official vendor / event pages
    "EVENT",
    "BLOG",
    "RSS",
    "FORUM",
    "REDDIT",
    "API",
]


class Settings(BaseSettings):
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str

    # Email
    resend_api_key: Optional[str] = None
    email_from: str = "VoucherBot <onboarding@resend.dev>"
    email_id: Optional[str] = None

    # Reddit
    reddit_client_id: Optional[str] = None
    reddit_client_secret: Optional[str] = None
    reddit_user_agent: Optional[str] = None
    reddit_fetch_interval_minutes: int = 3
    reddit_concurrency_limit: int = 5
    reddit_fetch_limit: int = 25

    # DB-driven scheduler
    tick_lease_ttl_seconds: int = 90
    tick_job_timeout_seconds: int = 45
    source_backoff_base_minutes: int = 5
    source_backoff_max_minutes: int = 360

    # AI providers
    gemini_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # Event matching (nested, not sourced from env — override in tests by
    # constructing Settings(event_matcher=EventMatcherConfig(...)))
    event_matcher: EventMatcherConfig = EventMatcherConfig()

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
