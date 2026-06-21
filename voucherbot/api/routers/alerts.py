from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.get("")
async def get_alerts() -> dict[str, str]:
    raise HTTPException(status_code=501, detail="Not Implemented")
