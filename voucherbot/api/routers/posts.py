from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/posts", tags=["posts"])

@router.get("")
async def get_posts() -> dict[str, str]:
    raise HTTPException(status_code=501, detail="Not Implemented")
