from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from config import settings
from core.auth import get_current_user
from bot.instagram import ig_client
import os

router = APIRouter(prefix="/api/settings", tags=["Settings"])

class SettingsUpdate(BaseModel):
    meta_app_id: Optional[str] = None
    meta_app_secret: Optional[str] = None
    meta_verify_token: Optional[str] = None
    page_access_token: Optional[str] = None
    instagram_account_id: Optional[str] = None
    webhook_base_url: Optional[str] = None
    dashboard_password: Optional[str] = None

class IceBreakerItem(BaseModel):
    question: str
    payload: str

class IceBreakerRequest(BaseModel):
    ice_breakers: List[IceBreakerItem]

def mask_token(token: str) -> str:
    if not token or len(token) < 8:
        return "Not Set" if not token else "••••••••"
    return f"{token[:4]}••••••••{token[-4:]}"

@router.get("")
async def get_settings(user: str = Depends(get_current_user)):
    return {
        "meta_app_id": settings.META_APP_ID or "",
        "meta_app_secret_configured": bool(settings.META_APP_SECRET),
        "meta_verify_token": settings.META_VERIFY_TOKEN,
        "page_access_token_masked": mask_token(settings.PAGE_ACCESS_TOKEN),
        "instagram_account_id": settings.INSTAGRAM_ACCOUNT_ID or "",
        "webhook_base_url": settings.WEBHOOK_BASE_URL or "",
        "webhook_endpoint": f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/webhook" if settings.WEBHOOK_BASE_URL else "/webhook",
        "api_version": settings.GRAPH_API_VERSION
    }

@router.post("")
async def update_settings(data: SettingsUpdate, user: str = Depends(get_current_user)):
    # Update settings instance and update ig_client
    if data.meta_app_id is not None:
        settings.META_APP_ID = data.meta_app_id
    if data.meta_app_secret is not None and data.meta_app_secret.strip():
        settings.META_APP_SECRET = data.meta_app_secret
    if data.meta_verify_token is not None and data.meta_verify_token.strip():
        settings.META_VERIFY_TOKEN = data.meta_verify_token
    if data.page_access_token is not None and data.page_access_token.strip():
        settings.PAGE_ACCESS_TOKEN = data.page_access_token
    if data.instagram_account_id is not None:
        settings.INSTAGRAM_ACCOUNT_ID = data.instagram_account_id
    if data.webhook_base_url is not None:
        settings.WEBHOOK_BASE_URL = data.webhook_base_url
    if data.dashboard_password is not None and data.dashboard_password.strip():
        settings.DASHBOARD_PASSWORD = data.dashboard_password

    # Update active client credentials
    ig_client.update_credentials(settings.PAGE_ACCESS_TOKEN, settings.INSTAGRAM_ACCOUNT_ID)

    # Persist to .env file
    try:
        env_lines = []
        if os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                env_lines = f.readlines()

        env_dict = {
            "META_APP_ID": settings.META_APP_ID,
            "META_APP_SECRET": settings.META_APP_SECRET,
            "META_VERIFY_TOKEN": settings.META_VERIFY_TOKEN,
            "PAGE_ACCESS_TOKEN": settings.PAGE_ACCESS_TOKEN,
            "INSTAGRAM_ACCOUNT_ID": settings.INSTAGRAM_ACCOUNT_ID,
            "WEBHOOK_BASE_URL": settings.WEBHOOK_BASE_URL,
            "DASHBOARD_PASSWORD": settings.DASHBOARD_PASSWORD,
            "JWT_SECRET": settings.JWT_SECRET,
            "HOST": settings.HOST,
            "PORT": str(settings.PORT),
            "DEBUG": str(settings.DEBUG)
        }

        with open(".env", "w", encoding="utf-8") as f:
            for k, v in env_dict.items():
                f.write(f"{k}={v}\n")
    except Exception as e:
        pass

    return {"message": "Settings updated successfully"}

@router.post("/test-connection")
async def test_meta_connection(user: str = Depends(get_current_user)):
    """Tests the current Page Access Token with Meta's Graph API."""
    res = await ig_client.verify_connection()
    return res

@router.post("/ice-breakers")
async def set_ice_breakers(data: IceBreakerRequest, user: str = Depends(get_current_user)):
    """Sets up to 4 conversation starter questions in the Instagram DM inbox."""
    payload = [item.dict() for item in data.ice_breakers]
    res = await ig_client.set_ice_breakers(payload)
    return res
