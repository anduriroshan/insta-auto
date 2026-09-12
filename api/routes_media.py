from fastapi import APIRouter, HTTPException, Depends
from core.auth import get_current_user
from bot.instagram import ig_client

router = APIRouter(prefix="/api/instagram", tags=["Instagram Media"])

@router.get("/media")
async def list_recent_media(limit: int = 25, user: str = Depends(get_current_user)):
    """
    Lists recent reels/posts from the connected IG account, for building a picker
    when scoping an automation rule's response to one specific reel.
    """
    try:
        return await ig_client.get_recent_media(limit=limit)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
