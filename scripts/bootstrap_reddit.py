import asyncio
import os
import sys

# Add the project root to the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from voucherbot.models.reddit import Subreddit, RedditKeyword
from voucherbot.config.settings import settings

subreddits = [
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
    "learnjava", "learnjavascript", "reactjs", "node", "SQL", "Database"
]

# Note: Removed duplicates like googlecloud/GoogleCloud, linux/Linux, database/Database manually

keywords = [
    "voucher", "coupon", "100% off", "discount", "free", "exam", "certification", "promo", "redeem"
]

async def bootstrap():
    engine = create_async_engine(settings.database_url)
    async_session = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session() as session:
        # Insert subreddits
        print("Inserting subreddits...")
        for sub in subreddits:
            stmt = insert(Subreddit).values(
                name=sub.lower(),
                enabled=True,
                priority=1
            ).on_conflict_do_nothing(index_elements=['name'])
            await session.execute(stmt)
            
        # Insert keywords
        print("Inserting keywords...")
        for kw in keywords:
            stmt = insert(RedditKeyword).values(
                keyword=kw.lower(),
                enabled=True,
                priority=1
            ).on_conflict_do_nothing(index_elements=['keyword'])
            await session.execute(stmt)
            
        await session.commit()
        print("Bootstrap complete!")

if __name__ == "__main__":
    asyncio.run(bootstrap())
