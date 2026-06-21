from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/sources", tags=["sources"])

@router.get("")
async def get_sources() -> dict[str, str]:
    raise HTTPException(status_code=501, detail="Not Implemented")
