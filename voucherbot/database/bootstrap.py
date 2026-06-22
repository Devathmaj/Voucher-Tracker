"""
Startup bootstrap: populates sources and keywords tables if empty.
Uses ON CONFLICT DO NOTHING so re-runs on every startup are safe and instant.
"""
import structlog
from sqlalchemy.dialects.postgresql import insert

from voucherbot.database.connection import AsyncSessionLocal
from voucherbot.models.source import Source, SourceType
from voucherbot.models.keyword import Keyword

logger = structlog.get_logger(__name__)

# ──────────────────────────────────────────────────────────────
# Keywords with scores
# ──────────────────────────────────────────────────────────────
KEYWORDS = [
    # High-value voucher/deal signals
    {"keyword": "voucher",           "score": 5},
    {"keyword": "coupon",            "score": 5},
    {"keyword": "100% off",          "score": 5},
    {"keyword": "promo code",        "score": 5},
    {"keyword": "free exam",         "score": 5},
    {"keyword": "free access",       "score": 4},
    {"keyword": "discount",          "score": 4},
    {"keyword": "redeem",            "score": 4},
    {"keyword": "50% off",           "score": 4},
    {"keyword": "limited time",      "score": 3},
    {"keyword": "beta access",       "score": 3},
    {"keyword": "free tier",         "score": 3},
    # Event signals
    {"keyword": "register now",      "score": 1},
    {"keyword": "webinar",           "score": 1},
    {"keyword": "virtual event",     "score": 1},
    {"keyword": "virtual training",  "score": 2},
    {"keyword": "free training",     "score": 2},
    {"keyword": "live session",      "score": 1},
    # General certification/learning signals
    {"keyword": "certification",     "score": 1},
    {"keyword": "exam",              "score": 1},
    {"keyword": "udemy",             "score": 1},
    {"keyword": "pearsonvue",        "score": 2},
    {"keyword": "aws",               "score": 1},
    {"keyword": "azure",             "score": 1},
    {"keyword": "google cloud",      "score": 1},
]

# ──────────────────────────────────────────────────────────────
# Reddit sources (one per subreddit)
# ──────────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    "AWSCertifications", "aws", "AzureCertification", "AZURE", "googlecloud",
    "CompTIA", "ccna", "cissp", "isc2", "kubernetes", "redhat", "LinuxCertifications",
    "ITCareerQuestions", "sysadmin", "networking", "devops", "docker", "terraform",
    "selfhosted", "cybersecurity", "netsec", "blueteamsec", "security", "AskNetsec",
    "oscp", "ethicalhacking", "hacking", "programming", "learnprogramming", "Python",
    "java", "golang", "javascript", "webdev", "cscareerquestions", "cscareerquestionsEU",
    "EngineeringStudents", "compsci", "csMajors", "MachineLearning", "artificial",
    "OpenAI", "LocalLLaMA", "GenAI", "freebies", "deals", "eFreebies", "FREE",
    "Udemy", "FreeUdemyCoupons", "AmazonWebServices", "MicrosoftLearn",
    "oracle", "OracleCloud", "google", "linux", "Ubuntu", "Fedora", "ArchLinux",
    "DataEngineering", "dataengineering", "datascience", "analytics", "database",
    "PostgreSQL", "mysql", "devsecops", "SRE", "cloud", "cloudcomputing",
    "learnmachinelearning", "artificialintelligence", "learnpython", "PowerShell",
    "bash", "git", "github", "vscode", "awsjobs", "AzureJobs", "remotework",
    "remotejobs", "jobs", "careerguidance", "resumes", "technology", "technews",
    "opensource", "FOSS", "homelab", "privacy", "InformationTechnology",
    "learnjava", "learnjavascript", "reactjs", "node", "SQL", "Database",
]

# ──────────────────────────────────────────────────────────────
# RSS feeds (Blogs, Forums, Aggregators)
# ──────────────────────────────────────────────────────────────
RSS_FEEDS = [
    # Official vendor blogs
    {"name": "AWS Training Blog",       "type": SourceType.BLOG,  "feed_url": "https://aws.amazon.com/blogs/training-and-certification/feed/"},
    {"name": "Microsoft Learn Blog",    "type": SourceType.BLOG,  "feed_url": "https://techcommunity.microsoft.com/t5/microsoft-learn-blog/bg-p/MicrosoftLearnBlog/rss"},
    {"name": "Google Cloud Blog",       "type": SourceType.BLOG,  "feed_url": "https://cloud.google.com/feeds/gcp-release-notes.xml"},
    {"name": "Cisco Learning Network",  "type": SourceType.BLOG,  "feed_url": "https://newsroom.cisco.com/c/services/i/servlets/newsroom/rssfeed.json"},
    {"name": "Linux Foundation Blog",   "type": SourceType.BLOG,  "feed_url": "https://www.linuxfoundation.org/blog/rss.xml"},
    {"name": "Red Hat Blog",            "type": SourceType.BLOG,  "feed_url": "https://www.redhat.com/en/rss/blog"},
    
    # Aggregators and generic tech sites
    {"name": "Dev.to Certifications",   "type": SourceType.RSS,   "feed_url": "https://dev.to/feed/tag/certification"},
    {"name": "Dev.to AWS",              "type": SourceType.RSS,   "feed_url": "https://dev.to/feed/tag/aws"},
    {"name": "Medium Certification",    "type": SourceType.RSS,   "feed_url": "https://medium.com/feed/tag/certification"},
    {"name": "Hacker News Cert Search", "type": SourceType.RSS,   "feed_url": "https://hnrss.org/newest?q=certification+OR+voucher+OR+free"},
]

# ──────────────────────────────────────────────────────────────
# Websites to scrape (Vendor Event Pages and specific forums)
# ──────────────────────────────────────────────────────────────
WEBSITES = [
    # Events
    {
        "name": "AWS Events",
        "type": SourceType.EVENT,
        "base_url": "https://aws.amazon.com/events/",
        "config": {
            "url": "https://aws.amazon.com/events/",
            "article_selector": ".lb-content-item",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "MS Virtual Training Days",
        "type": SourceType.EVENT,
        "base_url": "https://www.microsoft.com/en-us/trainingdays",
        "config": {
            "url": "https://www.microsoft.com/en-us/trainingdays",
            "article_selector": ".event-card",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "Google Cloud Events",
        "type": SourceType.EVENT,
        "base_url": "https://cloud.google.com/events",
        "config": {
            "url": "https://cloud.google.com/events",
            "article_selector": ".event-item",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "Oracle Univ Events",
        "type": SourceType.EVENT,
        "base_url": "https://education.oracle.com/events",
        "config": {
            "url": "https://education.oracle.com/events",
            "article_selector": ".event-listing",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "Cisco Live",
        "type": SourceType.EVENT,
        "base_url": "https://www.ciscolive.com/global.html",
        "config": {
            "url": "https://www.ciscolive.com/global.html",
            "article_selector": ".cmp-teaser",
            "title_selector": "h2",
            "link_selector": "a",
        },
    },
    {
        "name": "Red Hat Events",
        "type": SourceType.EVENT,
        "base_url": "https://www.redhat.com/en/events",
        "config": {
            "url": "https://www.redhat.com/en/events",
            "article_selector": ".rh-card",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    # Forums (if RSS isn't reliable, fallback to scraping)
    {
        "name": "MS Tech Community",
        "type": SourceType.FORUM,
        "base_url": "https://techcommunity.microsoft.com/",
        "config": {
            "url": "https://techcommunity.microsoft.com/t5/custom/page/page-id/Discussions",
            "article_selector": ".MessageList-item",
            "title_selector": ".message-subject",
            "link_selector": ".message-subject a",
        }
    },
]


async def bootstrap_data() -> None:
    """Populates sources and keywords tables on startup. Safe to re-run (idempotent)."""
    logger.info("Running database bootstrap...")
    async with AsyncSessionLocal() as session:

        # Keywords
        for kw in KEYWORDS:
            await session.execute(
                insert(Keyword)
                .values(keyword=kw["keyword"].lower(), score=kw["score"], enabled=True)
                .on_conflict_do_nothing(index_elements=["keyword"])
            )

        # Reddit sources
        for sub in REDDIT_SUBREDDITS:
            await session.execute(
                insert(Source)
                .values(
                    name=f"reddit:{sub.lower()}",
                    type=SourceType.REDDIT,
                    base_url=f"https://www.reddit.com/r/{sub}",
                    enabled=True,
                    priority=1,
                    config={"subreddit": sub},
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )

        # RSS feeds (includes BLOG and FORUM types via RSS)
        for feed in RSS_FEEDS:
            await session.execute(
                insert(Source)
                .values(
                    name=f"{feed['type'].value.lower()}:{feed['name'].lower().replace(' ', '_')}",
                    type=feed["type"],
                    base_url=feed["feed_url"],
                    enabled=True,
                    priority=1,
                    config={"feed_url": feed["feed_url"]},
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )

        # Websites (includes EVENT and FORUM types)
        for site in WEBSITES:
            await session.execute(
                insert(Source)
                .values(
                    name=f"{site['type'].value.lower()}:{site['name'].lower().replace(' ', '_')}",
                    type=site["type"],
                    base_url=site["base_url"],
                    enabled=True,
                    priority=1,
                    config=site["config"],
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )

        await session.commit()

    logger.info("Database bootstrap complete.")
