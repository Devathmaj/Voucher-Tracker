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
# RSS feeds from official certification / training providers
# ──────────────────────────────────────────────────────────────
RSS_FEEDS = [
    {"name": "AWS Training Blog",            "feed_url": "https://aws.amazon.com/blogs/training-and-certification/feed/"},
    {"name": "Microsoft Learn Blog",         "feed_url": "https://techcommunity.microsoft.com/plugins/custom/microsoft/o365/rss-feed?board=MicrosoftLearnBlog"},
    {"name": "Google Cloud Blog",            "feed_url": "https://cloud.google.com/feeds/gcp-release-notes.xml"},
    {"name": "Cisco Learning Network",       "feed_url": "https://learningnetwork.cisco.com/s/feeds/articles"},
    {"name": "CompTIA Blog",                 "feed_url": "https://www.comptia.org/blog/rss"},
    {"name": "Linux Foundation Blog",        "feed_url": "https://www.linuxfoundation.org/feed"},
    {"name": "HashiCorp Blog",               "feed_url": "https://www.hashicorp.com/blog/feed"},
    {"name": "Docker Blog",                  "feed_url": "https://www.docker.com/blog/feed/"},
    {"name": "Kubernetes Blog",              "feed_url": "https://kubernetes.io/feed.xml"},
    {"name": "CNCF Blog",                    "feed_url": "https://www.cncf.io/blog/feed/"},
    {"name": "Red Hat Blog",                 "feed_url": "https://www.redhat.com/en/rss/blog"},
    {"name": "ISC2 Blog",                    "feed_url": "https://www.isc2.org/Insights/feed"},
    {"name": "Offensive Security Blog",      "feed_url": "https://www.offsec.com/feed/"},
    {"name": "Udemy Business Blog",          "feed_url": "https://business.udemy.com/blog/feed/"},
]

# ──────────────────────────────────────────────────────────────
# Official certification websites to scrape
# ──────────────────────────────────────────────────────────────
WEBSITES = [
    {
        "name": "AWS Certification",
        "base_url": "https://aws.amazon.com/certification/",
        "config": {
            "url": "https://aws.amazon.com/certification/",
            "article_selector": ".lb-content-item",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "Microsoft Certifications",
        "base_url": "https://learn.microsoft.com/en-us/certifications/",
        "config": {
            "url": "https://learn.microsoft.com/en-us/certifications/",
            "article_selector": "li.card",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "Google Cloud Certifications",
        "base_url": "https://cloud.google.com/learn/certification",
        "config": {
            "url": "https://cloud.google.com/learn/certification",
            "article_selector": ".certification-card",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "CompTIA Certifications",
        "base_url": "https://www.comptia.org/certifications",
        "config": {
            "url": "https://www.comptia.org/certifications",
            "article_selector": ".certification-card",
            "title_selector": "h3",
            "link_selector": "a",
        },
    },
    {
        "name": "Cisco Certifications",
        "base_url": "https://www.cisco.com/c/en/us/training-events/training-certifications/certifications.html",
        "config": {
            "url": "https://www.cisco.com/c/en/us/training-events/training-certifications/certifications.html",
            "article_selector": ".card",
            "title_selector": "h3",
            "link_selector": "a",
        },
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

        # RSS feeds
        for feed in RSS_FEEDS:
            await session.execute(
                insert(Source)
                .values(
                    name=f"rss:{feed['name'].lower().replace(' ', '_')}",
                    type=SourceType.RSS,
                    base_url=feed["feed_url"],
                    enabled=True,
                    priority=1,
                    config={"feed_url": feed["feed_url"]},
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )

        # Websites
        for site in WEBSITES:
            await session.execute(
                insert(Source)
                .values(
                    name=f"web:{site['name'].lower().replace(' ', '_')}",
                    type=SourceType.WEBSITE,
                    base_url=site["base_url"],
                    enabled=True,
                    priority=1,
                    config=site["config"],
                )
                .on_conflict_do_nothing(index_elements=["name"])
            )

        await session.commit()

    logger.info("Database bootstrap complete.")
