"""
Stage 3 — Canonical Event Matching.

Given an ``ExtractedEvent`` produced by the AI analyzer, the ``EventMatcher``
determines whether the data describes an existing canonical ``Event`` (and
attaches the Post to it), or whether a brand-new Event should be created.

Matching is purely deterministic, operating on structured fields — never on
raw article text.

Scoring
-------
Configured via ``settings.event_matcher`` (an ``EventMatcherConfig`` instance):

  Field                 Default weight
  ──────────────────────────────────────────
  registration_url         +50   (exact normalised URL match)
  voucher_code             +40   (exact, case-normalised)
  promotion_name           +20   (token-overlap similarity >= name_threshold)
  vendor                   +15   (exact, lower-cased)
  certifications           +15   (at least one cert in common)
  date_overlap             +10   (date ranges overlap or are both absent)

Score bands (configurable thresholds):
  >= auto_merge_threshold (75)         → attach to existing Event
  >= possible_match_threshold (60)     → flag as POSSIBLE_MATCH (future review)
  <  possible_match_threshold          → create a new Event

Source Priority & Field Merging
--------------------------------
When an Event is updated by a new Post, fields are merged field-by-field
according to SOURCE_PRIORITY (defined in settings).  A higher-priority
source's non-null value takes precedence over an existing lower-priority
source's value.  The Event identity (id, created_at) is never changed.  An
audit entry is appended to ``event.merge_log`` for every update.

Provenance
----------
Posts are NEVER merged.  Many Posts may reference the same Event via the
``Post.event_id`` FK.  The ``Event.posts`` relationship provides full
provenance.
"""
from __future__ import annotations

import difflib
from datetime import datetime, timezone
from typing import Optional, Any

import structlog
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from voucherbot.config.settings import SOURCE_PRIORITY, settings
from voucherbot.models.event import Event, EventStatus, MatchConfidence
from voucherbot.models.post import Post
from voucherbot.models.source import SourceType
from voucherbot.services.ai.schema import ExtractedEvent
from voucherbot.services.ingestion.dedup import normalise_url

logger = structlog.get_logger(__name__)

# Scalar event fields that can be backfilled from incoming extraction data.
_MERGEABLE_FIELDS: tuple[str, ...] = (
    "vendor",
    "promotion_name",
    "promotion_type",
    "certifications",
    "voucher_code",
    "discount",
    "registration_url",
    "start_date",
    "end_date",
    "regions",
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _source_priority(source_type: SourceType) -> int:
    """Lower return value = higher authority (0 is most authoritative)."""
    try:
        return SOURCE_PRIORITY.index(source_type.value)
    except ValueError:
        return len(SOURCE_PRIORITY)  # unknown sources get lowest priority


def _name_similarity(a: Optional[str], b: Optional[str]) -> float:
    """Token-overlap similarity between two promotion names (0.0 – 1.0)."""
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _certs_overlap(a: Optional[list[str]], b: Optional[list[str]]) -> bool:
    if not a or not b:
        return False
    a_set = {c.upper() for c in a}
    b_set = {c.upper() for c in b}
    return bool(a_set & b_set)


def _dates_overlap(
    e_start: Optional[datetime],
    e_end: Optional[datetime],
    x_start: Optional[str],
    x_end: Optional[str],
) -> bool:
    """Return True if date ranges overlap, or if both have no dates (unknown)."""
    def _parse(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

    x_start_dt = _parse(x_start)
    x_end_dt = _parse(x_end)

    # If BOTH sides have no dates at all, consider it a weak match.
    if not any([e_start, e_end, x_start_dt, x_end_dt]):
        return True

    # Need at least one end-point from each side to check overlap.
    a_start = e_start or x_start_dt
    a_end = e_end or x_end_dt
    b_start = x_start_dt or e_start
    b_end = x_end_dt or e_end

    if a_start and b_end and a_start > b_end:
        return False
    if b_start and a_end and b_start > a_end:
        return False
    return True


def _score_candidate(event: Event, extracted: ExtractedEvent) -> int:
    """Compute a matching confidence score for ``extracted`` against ``event``."""
    cfg = settings.event_matcher
    score = 0

    # 1. registration_url — exact normalised URL match
    if event.registration_url and extracted.registration_url:
        if normalise_url(event.registration_url) == normalise_url(extracted.registration_url):
            score += cfg.weight_registration_url

    # 2. voucher_code — exact case-normalised match
    if event.voucher_code and extracted.voucher_code:
        if event.voucher_code.upper() == extracted.voucher_code.upper():
            score += cfg.weight_voucher_code

    # 3. vendor — exact lower-cased match
    if event.vendor and extracted.vendor:
        if event.vendor.lower() == extracted.vendor.lower():
            score += cfg.weight_vendor

    # 4. promotion_name — token-overlap similarity
    sim = _name_similarity(event.promotion_name, extracted.promotion_name)
    if sim >= cfg.name_similarity_threshold:
        score += cfg.weight_promotion_name

    # 5. certifications — at least one in common
    if _certs_overlap(event.certifications, extracted.certifications):
        score += cfg.weight_certifications

    # 6. date overlap
    if _dates_overlap(event.start_date, event.end_date, extracted.start_date, extracted.end_date):
        score += cfg.weight_date_overlap

    return score


def _merge_fields(
    event: Event,
    extracted: ExtractedEvent,
    source_type: SourceType,
    post_id: int,
    match_score: int,
    match_confidence: MatchConfidence,
) -> list[str]:
    """Merge non-null fields from ``extracted`` into ``event`` using source priority.

    Returns a list of field names that were actually updated.
    Updates event.merge_log with an audit entry.
    """
    incoming_priority = _source_priority(source_type)
    updated_fields: list[str] = []

    for field in _MERGEABLE_FIELDS:
        incoming_val = getattr(extracted, field, None)
        if incoming_val is None:
            continue  # nothing to contribute

        existing_val = getattr(event, field, None)

        if existing_val is None:
            # Backfill a missing field regardless of priority.
            setattr(event, field, incoming_val)
            updated_fields.append(field)
        else:
            # Existing value present: only overwrite if the incoming source has
            # higher authority.
            existing_priority = _get_event_field_source_priority(event, field)
            if incoming_priority < existing_priority:
                setattr(event, field, incoming_val)
                updated_fields.append(field)

    # --- Append audit log entry ---
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_type": source_type.value,
        "post_id": post_id,
        "match_score": match_score,
        "match_confidence": match_confidence.value,
        "fields_updated": updated_fields,
    }
    current_log: list[Any] = event.merge_log or []
    event.merge_log = current_log + [log_entry]

    return updated_fields


def _get_event_field_source_priority(event: Event, field: str) -> int:
    """Determine the effective source priority for an existing event field.

    We look at the merge_log in reverse (most recent first) to find which
    source last set this field.  If unknown, assume lowest priority so any
    incoming data can overwrite.
    """
    for entry in reversed(event.merge_log or []):
        if field in (entry.get("fields_updated") or []):
            source_type_val = entry.get("source_type", "")
            try:
                return SOURCE_PRIORITY.index(source_type_val)
            except ValueError:
                pass
    # Field was set during Event creation (first post) — look at the first
    # log entry if it exists.
    first_entry = (event.merge_log or [None])[0]
    if first_entry:
        source_type_val = first_entry.get("source_type", "")
        try:
            return SOURCE_PRIORITY.index(source_type_val)
        except ValueError:
            pass
    return len(SOURCE_PRIORITY)  # unknown → lowest priority


def _extracted_to_event_fields(extracted: ExtractedEvent) -> dict[str, Any]:
    """Map an ExtractedEvent to a dict of Event column values."""
    def _parse_date(s: Optional[str]) -> Optional[datetime]:
        if not s:
            return None
        try:
            dt = datetime.fromisoformat(s)
            return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

    return {
        "vendor": extracted.vendor,
        "promotion_name": extracted.promotion_name,
        "promotion_type": extracted.promotion_type,
        "certifications": extracted.certifications,
        "voucher_code": extracted.voucher_code,
        "discount": extracted.discount,
        "registration_url": extracted.registration_url,
        "start_date": _parse_date(extracted.start_date),
        "end_date": _parse_date(extracted.end_date),
        "regions": extracted.regions,
    }


# ---------------------------------------------------------------------------
# EventMatcher
# ---------------------------------------------------------------------------

class EventMatcher:
    """Match AI-extracted post data to a canonical Event, or create a new one.

    Usage::

        matcher = EventMatcher()
        event, confidence = await matcher.match_or_create(
            db, extracted, post, source_type
        )
    """

    async def _find_candidates(
        self, db: AsyncSession, extracted: ExtractedEvent
    ) -> list[Event]:
        """Retrieve a small set of candidate Events to score against.

        Uses indexed columns (registration_url, voucher_code, vendor) to avoid
        a full-table scan.  Only ACTIVE events are considered.
        """
        filters = []
        if extracted.registration_url:
            filters.append(Event.registration_url == extracted.registration_url)
        if extracted.voucher_code:
            filters.append(Event.voucher_code == extracted.voucher_code.upper())
        if extracted.vendor:
            filters.append(Event.vendor == extracted.vendor.lower())

        if not filters:
            return []

        result = await db.execute(
            select(Event)
            .where(Event.status == EventStatus.ACTIVE)
            .where(or_(*filters))
            .limit(20)
        )
        return list(result.scalars().all())

    async def match_or_create(
        self,
        db: AsyncSession,
        extracted: ExtractedEvent,
        post: Post,
        source_type: SourceType,
    ) -> tuple[Event, MatchConfidence]:
        """Find or create a canonical Event for ``extracted`` and link ``post``.

        Returns the Event and the MatchConfidence used.
        """
        cfg = settings.event_matcher
        candidates = await self._find_candidates(db, extracted)

        best_event: Optional[Event] = None
        best_score = 0

        for candidate in candidates:
            score = _score_candidate(candidate, extracted)
            if score > best_score:
                best_score = score
                best_event = candidate

        # --- Determine confidence band ---
        if best_score >= cfg.auto_merge_threshold and best_event is not None:
            confidence = MatchConfidence.AUTO_MERGED
        elif best_score >= cfg.possible_match_threshold and best_event is not None:
            confidence = MatchConfidence.POSSIBLE_MATCH
        else:
            confidence = MatchConfidence.NEW
            best_event = None  # ignore low-confidence candidates

        if best_event is not None:
            # --- Attach to existing Event ---
            updated = _merge_fields(
                best_event, extracted, source_type, post.id, best_score, confidence
            )
            logger.info(
                "event_matcher: attached post to existing event",
                event_id=best_event.id,
                post_id=post.id,
                score=best_score,
                confidence=confidence.value,
                fields_updated=updated,
            )
        else:
            # --- Create new canonical Event ---
            fields = _extracted_to_event_fields(extracted)
            best_event = Event(**fields, status=EventStatus.ACTIVE)
            db.add(best_event)
            await db.flush()  # populate best_event.id before writing merge_log

            first_log_entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source_type": source_type.value,
                "post_id": post.id,
                "match_score": 0,
                "match_confidence": MatchConfidence.NEW.value,
                "fields_updated": [f for f in _MERGEABLE_FIELDS if fields.get(f) is not None],
            }
            best_event.merge_log = [first_log_entry]

            logger.info(
                "event_matcher: created new event",
                event_id=best_event.id,
                post_id=post.id,
                vendor=extracted.vendor,
                promotion_name=extracted.promotion_name,
            )

        post.event_id = best_event.id
        return best_event, confidence
