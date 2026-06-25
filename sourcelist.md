# VoucherBot Source List

Auto-generated from `voucherbot/database/bootstrap.py` and runtime settings.

## How fetching works

- **Scheduler:** one DB-driven tick every **2 minutes**; each tick processes **exactly one source** (whichever is most overdue).
- **Fetch limit:** max items requested from the collector **per poll** (before keyword filtering, dedup, and AI).
- **Reddit fetch limit:** `settings.reddit_fetch_limit` = **25** posts/search
- **All other sources:** default fetch limit = **25** items per poll
- **Keyword filter:** posts scoring below threshold are dropped after fetch (not stored).
- **Tier cadence defaults:** A=15 min, B=60 min, C=240 min (4 h), D=720 min (12 h)

## Tier summary

| Tier | Poll interval | Queue priority | Sources | ~Max items/day (tier total) |
|------|---------------|----------------|---------|------------------------------|
| A | every 15 min | Highest first | 8 | ~19,200 |
| B | every 1 h (60 min) | Highest first | 24 | ~14,400 |
| C | every 4 h (240 min) | Highest first | 7 | ~1,050 |
| D | every 12 h (720 min) | Highest first | 10 | ~500 |

**Total configured sources: 49**

> **Live DB note:** Your Postgres database currently has **118 sources** from an older catalog (including ~100 extra Reddit subs not in bootstrap). Bootstrap uses `on_conflict_do_nothing`, so legacy rows remain. This file reflects the **current code configuration** only. Re-run `python scripts/generate_sourcelist.py` after bootstrap changes.

## All sources

| Source | Type | Tier | Poll interval | Items/poll | ~Max items/day | Collector | URL |
|--------|------|------|---------------|------------|----------------|-----------|-----|
| reddit:awscertifications | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/AWSCertifications |
| reddit:azurecertification | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/AzureCertification |
| reddit:deals | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/deals |
| reddit:efreebies | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/eFreebies |
| reddit:free | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/FREE |
| reddit:freebies | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/freebies |
| reddit:freeudemycoupons | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/FreeUdemyCoupons |
| reddit:udemy | REDDIT | A | every 15 min | 25 | 2400 | RedditCollector | https://www.reddit.com/r/Udemy |
| blog:aws_training_and_certification_blog | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://aws.amazon.com/blogs/training-and-certification/feed/ |
| blog:aws_training_announcements | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://aws.amazon.com/blogs/training-and-certification/category/po... |
| blog:cisco_newsroom | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json |
| blog:google_cloud_blog | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://cloudblog.withgoogle.com/rss/ |
| blog:linux_foundation_blog | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://www.linuxfoundation.org/blog/rss.xml |
| blog:microsoft_events | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/board?board... |
| blog:microsoft_learn_blog | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://techcommunity.microsoft.com/t5/s/gxcuf89792/rss/Community?i... |
| blog:red_hat_blog | BLOG | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://www.redhat.com/en/rss/blog |
| reddit:ccna | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/ccna |
| reddit:cissp | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/cissp |
| reddit:comptia | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/CompTIA |
| reddit:googlecloud | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/googlecloud |
| reddit:isc2 | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/isc2 |
| reddit:kubernetes | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/kubernetes |
| reddit:linuxcertifications | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/LinuxCertifications |
| reddit:microsoftlearn | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/MicrosoftLearn |
| reddit:oraclecloud | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/OracleCloud |
| reddit:redhat | REDDIT | B | every 1 h (60 min) | 25 | 600 | RedditCollector | https://www.reddit.com/r/redhat |
| rss:aws_builder | RSS | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://builder.aws.com/rss.xml |
| rss:cisco_newsroom | RSS | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json |
| rss:cisco_newsroom_press | RSS | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.j... |
| rss:cisco_newsroom_security | RSS | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.j... |
| rss:linux.com | RSS | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://www.linux.com/feed/ |
| rss:microsoft_blog | RSS | B | every 1 h (60 min) | 25 | 600 | RssCollector | https://blogs.microsoft.com/feed |
| forum:google_cloud_training_group | FORUM | C | every 4 h (240 min) | 25 | 150 | RssCollector | https://discuss.google.dev/c/google-cloud/cloud-announcements/172.rss |
| forum:microsoft_learn_qanda_voucher_search | FORUM | C | every 4 h (240 min) | 25 | 150 | RssCollector | https://learn.microsoft.com/api/search/rss?search=voucher+certifica... |
| rss:packet_pilot | RSS | C | every 4 h (240 min) | 25 | 150 | RssCollector | https://packetpilot.com/feed/ |
| rss:tutorials_dojo | RSS | C | every 4 h (240 min) | 25 | 150 | RssCollector | https://tutorialsdojo.com/feed/ |
| rss:cloud_academy_blog | WEBSITE | C | every 4 h (240 min) | 25 | 150 | WebsiteCollector | https://www.pluralsight.com/resources/blog |
| website:msfthub_vouchers | WEBSITE | C | every 4 h (240 min) | 25 | 150 | WebsiteCollector | https://msfthub.com/vouchers/ |
| website:vladtalkstech | WEBSITE | C | every 4 h (240 min) | 25 | 150 | WebsiteCollector | https://vladtalkstech.com/ |
| blog:oracle_university_blog | BLOG | D | every 12 h (720 min) | 25 | 50 | RssCollector | https://feeds.libsyn.com/459162/rss |
| event:aws_events | EVENT | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://aws.amazon.com/events/ |
| event:aws_reinvent | EVENT | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://aws.amazon.com/events/reinvent/ |
| event:cisco_live | EVENT | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://www.ciscolive.com/global.html |
| event:google_cloud_events | EVENT | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://cloud.google.com/events |
| event:google_cloud_next | EVENT | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://cloud.withgoogle.com/next |
| event:microsoft_cloud_skills_challenge | EVENT | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://learn.microsoft.com/training/challenges |
| website:comptia_offers | WEBSITE | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://www.comptia.org/en-us/blog/ |
| website:isc2_blog | WEBSITE | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://www.isc2.org/Insights |
| website:red_hat_training_specials | WEBSITE | D | every 12 h (720 min) | 25 | 50 | WebsiteCollector | https://www.redhat.com/en/services/training/specials |

## Notes

- **reddit:awscertifications:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:azurecertification:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:deals:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:efreebies:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:free:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:freebies:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:freeudemycoupons:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:udemy:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:ccna:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:cissp:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:comptia:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:googlecloud:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:isc2:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:kubernetes:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:linuxcertifications:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:microsoftlearn:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:oraclecloud:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **reddit:redhat:** Keyword search (OR of query_terms) when PRAW configured; else RSS fallback
- **forum:google_cloud_training_group:** Migrated from Google Groups to discuss.google.dev. Category 172 = Cloud Announcements.
- **rss:cloud_academy_blog:** No RSS exists. Scrapes blog listing page. Selector may need tuning - inspect live page if 0 items returned.
- **blog:oracle_university_blog:** Podcast RSS - blog /rss is 403. Podcast actively covers Race to Certification and free exam promos.
