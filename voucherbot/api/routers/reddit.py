from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from voucherbot.database.init_db import get_db
from voucherbot.models.reddit import RedditPost
from voucherbot.services.scheduler import scheduled_reddit_sync

router = APIRouter(prefix="/reddit", tags=["reddit"])

@router.get("/status")
async def get_status():
    """Health endpoint returning sync status."""
    # This could be expanded to query DB for last sync time
    return {"status": "ok", "message": "Reddit ingestion pipeline is active."}

@router.get("/posts")
async def get_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Returns a paginated list of posts directly from the database."""
    result = await db.execute(
        select(RedditPost)
        .order_by(RedditPost.created_utc.desc())
        .offset(skip)
        .limit(limit)
    )
    posts = result.scalars().all()
    return [
        {
            "id": p.id, 
            "title": p.title, 
            "url": p.url,
            "status": p.status.value, 
            "created_utc": p.created_utc
        } for p in posts
    ]

@router.get("/posts/{post_id}")
async def get_post(post_id: str, db: AsyncSession = Depends(get_db)):
    """Returns a single post from the database."""
    result = await db.execute(select(RedditPost).where(RedditPost.id == post_id))
    post = result.scalars().first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return {
        "id": post.id, 
        "title": post.title, 
        "body": post.body,
        "status": post.status.value
    }

@router.post("/sync", include_in_schema=False)
async def manual_sync(background_tasks: BackgroundTasks):
    """Admin endpoint to manually trigger sync process."""
    background_tasks.add_task(scheduled_reddit_sync)
    return {"message": "Sync triggered in the background"}
