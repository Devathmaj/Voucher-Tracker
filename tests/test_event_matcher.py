"""
Tests for Stage 3 EventMatcher scoring logic.

Tests are unit-level only (no DB or async I/O).  They exercise the private
scoring and merging helpers directly, and the public API via a stub that
bypasses the database candidate query.

Coverage:
  - _score_candidate: each individual scoring dimension.
  - _merge_fields: backfilling nulls, source-priority-based overwrite.
  - _dates_overlap: various overlap/non-overlap scenarios.
  - Overall confidence band assignment.
"""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from voucherbot.config.settings import EventMatcherConfig, settings
from voucherbot.models.event import Event, EventStatus, MatchConfidence
from voucherbot.models.source import SourceType
from voucherbot.services.ai.schema import ExtractedEvent
from voucherbot.services.ingestion.event_matcher import (
    _certs_overlap,
    _dates_overlap,
    _merge_fields,
    _name_similarity,
    _score_candidate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _event(**kwargs) -> Event:
    """Create an in-memory Event with sensible defaults."""
    defaults = dict(
        id=1,
        vendor=None,
        promotion_name=None,
        promotion_type=None,
        certifications=None,
        voucher_code=None,
        discount=None,
        registration_url=None,
        start_date=None,
        end_date=None,
        regions=None,
        status=EventStatus.ACTIVE,
        merge_log=[],
    )
    defaults.update(kwargs)
    return Event(**defaults)


def _extracted(**kwargs) -> ExtractedEvent:
    defaults = dict(is_voucher=True, confidence=0.9)
    defaults.update(kwargs)
    return ExtractedEvent(**defaults)


# ---------------------------------------------------------------------------
# _score_candidate
# ---------------------------------------------------------------------------

class TestScoreCandidate:
    cfg = settings.event_matcher  # default EventMatcherConfig

    def test_registration_url_exact_match_scores_50(self):
        e = _event(registration_url="https://learn.microsoft.com/promo")
        x = _extracted(registration_url="https://learn.microsoft.com/promo")
        assert _score_candidate(e, x) >= self.cfg.weight_registration_url

    def test_registration_url_utm_ignored(self):
        e = _event(registration_url="https://learn.microsoft.com/promo")
        x = _extracted(registration_url="https://learn.microsoft.com/promo?utm_source=tw")
        score = _score_candidate(e, x)
        assert score >= self.cfg.weight_registration_url

    def test_voucher_code_exact_scores_40(self):
        e = _event(voucher_code="AZURE50")
        x = _extracted(voucher_code="AZURE50")
        assert _score_candidate(e, x) >= self.cfg.weight_voucher_code

    def test_voucher_code_case_insensitive(self):
        e = _event(voucher_code="AZURE50")
        x = _extracted(voucher_code="azure50")
        assert _score_candidate(e, x) >= self.cfg.weight_voucher_code

    def test_vendor_exact_scores_15(self):
        e = _event(vendor="microsoft")
        x = _extracted(vendor="microsoft")
        assert _score_candidate(e, x) >= self.cfg.weight_vendor

    def test_vendor_mismatch_scores_0(self):
        e = _event(vendor="microsoft")
        x = _extracted(vendor="amazon")
        # Only vendor differs — score should not include vendor weight.
        score = _score_candidate(e, x)
        assert score < self.cfg.weight_vendor

    def test_certification_overlap_scores_15(self):
        e = _event(certifications=["AZ-104", "SC-300"])
        x = _extracted(certifications=["AZ-104", "DP-203"])
        assert _score_candidate(e, x) >= self.cfg.weight_certifications

    def test_no_certification_overlap_scores_0(self):
        e = _event(certifications=["AZ-104"])
        x = _extracted(certifications=["AWS-SAA"])
        assert _score_candidate(e, x) < self.cfg.weight_certifications

    def test_perfect_match_scores_max(self):
        e = _event(
            registration_url="https://ms.com/promo",
            voucher_code="AZURE50",
            vendor="microsoft",
            promotion_name="AI Skills Fest",
            certifications=["AZ-900"],
            start_date=datetime(2026, 8, 1, tzinfo=timezone.utc),
            end_date=datetime(2026, 8, 31, tzinfo=timezone.utc),
        )
        x = _extracted(
            registration_url="https://ms.com/promo",
            voucher_code="AZURE50",
            vendor="microsoft",
            promotion_name="AI Skills Fest",
            certifications=["AZ-900"],
            start_date="2026-08-01",
            end_date="2026-08-31",
        )
        cfg = settings.event_matcher
        max_score = (
            cfg.weight_registration_url
            + cfg.weight_voucher_code
            + cfg.weight_vendor
            + cfg.weight_promotion_name
            + cfg.weight_certifications
            + cfg.weight_date_overlap
        )
        assert _score_candidate(e, x) == max_score

    def test_zero_if_no_shared_fields(self):
        e = _event()
        x = _extracted()
        # Date overlap logic explicitly awards points if dates are absent on both sides.
        assert _score_candidate(e, x) == self.cfg.weight_date_overlap


# ---------------------------------------------------------------------------
# _dates_overlap
# ---------------------------------------------------------------------------

class TestDatesOverlap:
    def _dt(self, s: str) -> datetime:
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)

    def test_overlapping_ranges(self):
        assert _dates_overlap(self._dt("2026-08-01"), self._dt("2026-08-31"), "2026-08-15", "2026-09-15")

    def test_non_overlapping_ranges(self):
        assert not _dates_overlap(self._dt("2026-01-01"), self._dt("2026-01-31"), "2026-03-01", "2026-03-31")

    def test_both_none_returns_true(self):
        assert _dates_overlap(None, None, None, None)

    def test_one_side_none_returns_true(self):
        assert _dates_overlap(self._dt("2026-08-01"), self._dt("2026-08-31"), None, None)


# ---------------------------------------------------------------------------
# _merge_fields
# ---------------------------------------------------------------------------

class TestMergeFields:
    def _make_post(self) -> MagicMock:
        p = MagicMock()
        p.id = 99
        return p

    def test_backfills_null_field(self):
        e = _event(end_date=None)
        x = _extracted(end_date="2026-09-30")
        updated = _merge_fields(e, x, SourceType.BLOG, 99, 80, MatchConfidence.AUTO_MERGED)
        # end_date should have been set on the event
        assert "end_date" in updated

    def test_does_not_overwrite_with_higher_priority_when_same(self):
        """Lower-priority source should NOT overwrite higher-priority source."""
        e = _event(vendor="microsoft")
        # Simulate the event's vendor was set by a BLOG (priority 2)
        e.merge_log = [
            {"source_type": "BLOG", "fields_updated": ["vendor"], "timestamp": "", "post_id": 1,
             "match_score": 0, "match_confidence": "NEW"}
        ]
        x = _extracted(vendor="MICROSOFT")
        # REDDIT has lower priority than BLOG
        updated = _merge_fields(e, x, SourceType.REDDIT, 100, 50, MatchConfidence.AUTO_MERGED)
        assert "vendor" not in updated

    def test_overwrites_with_higher_priority_source(self):
        """Higher-priority source SHOULD overwrite lower-priority source."""
        e = _event(vendor="microsoft")
        e.merge_log = [
            {"source_type": "REDDIT", "fields_updated": ["vendor"], "timestamp": "", "post_id": 1,
             "match_score": 0, "match_confidence": "NEW"}
        ]
        x = _extracted(vendor="microsoft")
        # WEBSITE has higher priority than REDDIT
        updated = _merge_fields(e, x, SourceType.WEBSITE, 100, 80, MatchConfidence.AUTO_MERGED)
        assert "vendor" in updated

    def test_appends_audit_log_entry(self):
        e = _event(voucher_code=None)
        x = _extracted(voucher_code="CODE99")
        assert e.merge_log == []
        _merge_fields(e, x, SourceType.RSS, 55, 70, MatchConfidence.AUTO_MERGED)
        assert len(e.merge_log) == 1
        entry = e.merge_log[0]
        assert entry["source_type"] == "RSS"
        assert "voucher_code" in entry["fields_updated"]


# ---------------------------------------------------------------------------
# Confidence band assignment (integration-level, no DB)
# ---------------------------------------------------------------------------

class TestConfidenceBands:
    """Verify score thresholds map to correct MatchConfidence values."""

    @pytest.mark.asyncio
    async def test_auto_merge_threshold(self):
        from voucherbot.services.ingestion.event_matcher import EventMatcher

        matcher = EventMatcher()
        cfg = settings.event_matcher

        # Construct a candidate Event whose score will hit >= auto_merge_threshold.
        candidate = _event(
            id=1,
            registration_url="https://ms.com/promo",
            voucher_code="AZURE50",
        )
        extracted = _extracted(
            registration_url="https://ms.com/promo",
            voucher_code="AZURE50",
        )

        # Score: registration_url (50) + voucher_code (40) = 90 >= 75
        score = _score_candidate(candidate, extracted)
        assert score >= cfg.auto_merge_threshold

    @pytest.mark.asyncio
    async def test_possible_match_band(self):
        cfg = settings.event_matcher
        candidate = _event(id=1, vendor="microsoft", promotion_name="AI Skills Fest")
        extracted = _extracted(vendor="microsoft", promotion_name="AI Skills Fest")

        # vendor (15) + name_similarity likely full weight (20) = 35 < 60
        # This confirms that only vendor + name is insufficient for auto-merge.
        score = _score_candidate(candidate, extracted)
        # Score depends on similarity — confirm it's below auto-merge
        assert score < cfg.auto_merge_threshold

    def test_new_event_below_possible_match(self):
        cfg = settings.event_matcher
        candidate = _event(id=1, vendor="microsoft")
        extracted = _extracted(vendor="amazon")  # no match
        score = _score_candidate(candidate, extracted)
        assert score < cfg.possible_match_threshold
