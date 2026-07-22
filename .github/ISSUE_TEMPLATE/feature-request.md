---
name: Feature Request
about: Suggest a new feature or improvement for VoucherBot
title: "[FEAT] "
labels: enhancement
assignees: ''
---

## Problem Statement

<!-- What problem does this feature solve? Why is it needed? -->

## Proposed Solution

<!-- Describe the feature you'd like. Be as specific as you can. -->

## Affected Area

<!-- Check all that apply -->

- [ ] Scheduler / Dispatcher
- [ ] HTTP Policy Layer (`http_policy.py`)
- [ ] RSS Collector
- [ ] Website Collector
- [ ] Reddit Integration
- [ ] AI Layer (Groq / Gemini)
- [ ] Email Notifications
- [ ] Database / Migrations
- [ ] API / Routers
- [ ] Configuration / Settings
- [ ] Other: 

## Policy-Sensitive Files

<!-- If your proposal touches any of the files below, explain how the ethical and legal obligations described in CONTRIBUTING.md are preserved. Delete this section if not applicable. -->

- [ ] This feature touches `http_policy.py`, `reddit/client.py`, `reddit/collector.py`, or `scheduler.py`

If checked, please confirm:

- [ ] `robots.txt` compliance is preserved.
- [ ] No default crawl delays are reduced.
- [ ] Reddit rate limits and the Responsible Builder Policy are respected.
- [ ] `REDDIT_INGESTION_ENABLED=false` still results in a clean no-op.

**Explanation:**
<!-- How does your proposal preserve these obligations? -->

## Alternatives Considered

<!-- Have you considered any alternative approaches? Why did you prefer this one? -->

## Additional Notes

<!-- Mockups, references, prior art, or anything else that might help. -->