# Voucher Source Implementation Gap Checklist

Based on `deep-research-report.md` and the current app code.

## Current Implementation Count

Report checklist coverage:

- Fully implemented: 1 of 6
- Partially implemented: 4 of 6
- Not implemented: 1 of 6

Source coverage from the report:

- Vendor official channels: most report vendors now have seeded RSS/page sources; selectors and live-source validation still need follow-up.
- Community/forum coverage: Reddit, Microsoft Learn Q&A RSS/search, and Google Groups Atom are seeded; AWS re:Post and specialized forum collectors are still missing.
- Aggregator blogs named in the report: major named feeds/pages are now seeded in startup bootstrap.

## Already Implemented Or Partially Implemented

- Vendor RSS/blog ingestion exists through `RssCollector` and seeded RSS/blog sources.
- Vendor event-page scraping exists through `WebsiteCollector` and seeded event sources.
- Reddit collection exists through `RedditCollector` and seeded subreddit sources.
- Scheduler jobs exist for Reddit, RSS, blogs, forums, and events.
- Compile/deduplicate exists through the shared ingestion pipeline and unique `(source_id, external_id)` constraint.
- Keyword scoring and AI analysis exist for newly inserted matching posts.

## Missing Checklist

### Official Vendor Sources

- [x] Add a Microsoft Learn Q&A source for voucher/certification queries, preferably via RSS/Atom or a supported API rather than the generic Tech Community discussion page.
- [ ] Add explicit Microsoft Build, Ignite, and Cloud Skills Challenge event pages with selectors tested against the real pages.
- [x] Seed explicit Microsoft Build, Ignite, and Cloud Skills Challenge event pages.
- [ ] Verify or replace the Microsoft Learn Blog RSS URL currently seeded, and add a health check for broken feeds.
- [x] Replace the current generic AWS event/blog coverage with report-specific AWS Training & Certification announcement feeds, including category feed support.
- [ ] Add AWS re:Post search/API ingestion for voucher/free-exam terms.
- [ ] Add Cisco Learning Network or official Cisco education/safeguard offer monitoring where public access is available.
- [x] Add Cisco Press or other report-mentioned Cisco RSS fallback sources if Cisco Learning Network remains login-gated.
- [x] Add CompTIA official offer/news page scraping.
- [x] Add ISC2 public community/blog monitoring where publicly accessible.
- [x] Add Google Cloud certification/forum monitoring, especially Google Groups Atom/RSS if available.
- [x] Replace or supplement the current Google Cloud release-notes feed with the report's broader Google Cloud blog RSS and certification/event sources.
- [x] Add Oracle University offer/free-quiz voucher page scraping, not only generic Oracle events.
- [x] Add Red Hat Training specials page scraping for offers like retake/referral discounts.

### Community And Forum Sources

- [x] Narrow the Reddit subreddit seed list to high-signal certification communities from the report, or tag/prioritize them separately from broad tech/job subreddits.
- [x] Add Reddit JSON/RSS unauthenticated fallback support, since the current implementation requires Async PRAW credentials.
- [x] Add per-source query terms for Reddit instead of only fetching `/new` and filtering after collection.
- [x] Add Microsoft Learn Q&A tag/search feeds for "voucher", "exam voucher", and certification terms.
- [ ] Add AWS re:Post query ingestion on a weekly cadence.
- [x] Add Google Groups Atom/RSS ingestion for Google Cloud training/certification forums.
- [ ] Add forum-specific collectors for Discourse/Jive-style forums if the generic website collector cannot reliably parse them.

### Aggregator Blogs Named In The Report

- [x] Add MSFTHub scraping for voucher/news pages.
- [x] Add VladTalksTech scraping or feed discovery.
- [x] Add Tutorials Dojo RSS: `https://tutorialsdojo.com/feed/`.
- [x] Add CertMag RSS: `https://certmag.com/feed/`.
- [x] Add Packet Pilot RSS/feed discovery.
- [x] Add Cloud Academy or A Cloud Guru blog RSS/feed discovery.
- [x] Add HackerDNA RSS: `https://hackerdna.com/feed`.
- [ ] Add ExamPro or other smaller aggregator sources after validating signal quality.
- [ ] Leave Certification Station/Discord as manual or explicit bot integration only, because the report flags automation as higher ToS risk.

### Cadence And Scheduling

- [x] Move cadence to per-source configuration instead of fixed source-type intervals.
- [ ] Match the report's intended cadence: Reddit daily, active RSS/blogs daily or weekly, slower forums weekly, event pages weekly around major events.
- [ ] Add event-season scheduling windows for Build, Ignite, re:Invent, Google Cloud Next, and Cisco Live.
- [ ] Add backoff/disable behavior for sources with repeated failures.
- [ ] Add observability for last successful fetch, last error, fetched count, new count, duplicate count, and AI-analyzed count per source.

### Data Quality And Extraction

- [ ] Store extracted voucher metadata as first-class fields: vendor, exam/certification, discount percent, voucher code, expiry date, eligibility, region, source confidence.
- [ ] Add expiry-date extraction and filtering.
- [ ] Add vendor/category tagging beyond simple keyword scoring.
- [ ] Add source reliability/priority scoring based on the report's reliability and ToS assessment.
- [ ] Add duplicate detection across different sources by canonical URL/title/code, not only within the same source.
- [ ] Add full article fetching for RSS items when the feed summary is too sparse.
- [ ] Add selector tests/fixtures for every website source.

### Product/API Surface

- [x] Implement `GET /sources`; it currently returns `501 Not Implemented`.
- [x] Implement `GET /posts`; it currently returns `501 Not Implemented`.
- [x] Implement `GET /alerts`; it currently returns `501 Not Implemented`.
- [ ] Decide whether to delete or repair `voucherbot/api/routers/reddit.py`; it references missing Reddit-specific models/services and is not mounted.
- [ ] Add manual sync endpoints for mounted source types if operators need to trigger collection.
- [ ] Add filtering endpoints for confirmed vouchers, pending AI review, vendor, source type, confidence, and expiry.

### Notifications

- [ ] Wire confirmed AI-positive vouchers into email notifications.
- [ ] Mark notified posts as `NOTIFIED`.
- [ ] Add notification deduplication so the same voucher is not emailed repeatedly.
- [ ] Add a digest mode for daily/weekly summaries.

### Compliance And Operations

- [ ] Add a ToS/compliance review note per source, especially for login-gated forums and Discord/Slack.
- [ ] Skip or explicitly manualize Discord/Slack scraping unless an approved bot/API workflow is added.
- [ ] Add rate-limit settings per source/provider.
- [ ] Add tests for RSS, website, Reddit, pipeline deduplication, scheduler registration, and API routes.
