import httpx
import logging
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger("instagram_api")

class InstagramGraphAPI:
    def __init__(self, page_access_token: Optional[str] = None, ig_account_id: Optional[str] = None):
        self.access_token = page_access_token or settings.PAGE_ACCESS_TOKEN
        self.ig_account_id = ig_account_id or settings.INSTAGRAM_ACCOUNT_ID
        self.page_id = settings.PAGE_ID

    @property
    def base_url(self) -> str:
        if self.access_token and self.access_token.startswith("IG"):
            return f"https://graph.instagram.com/{settings.GRAPH_API_VERSION}"
        return f"{settings.GRAPH_API_BASE}/{settings.GRAPH_API_VERSION}"

    @property
    def target_endpoint(self) -> str:
        if self.access_token and self.access_token.startswith("IG"):
            return "me"
        return self.page_id or "me"

    def update_credentials(self, token: str, account_id: str):
        self.access_token = token
        self.ig_account_id = account_id

    async def send_dm(self, recipient_id: str, text: str, media_url: Optional[str] = None) -> Dict[str, Any]:
        """
        Sends a standard direct message to a user by scoped ID.
        Uses POST /{target}/messages
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        url = f"{self.base_url}/{self.target_endpoint}/messages"
        params = {"access_token": self.access_token}
        
        payload: Dict[str, Any] = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE"
        }

        if media_url:
            # Send media message (image/video attachment)
            payload["message"] = {
                "attachment": {
                    "type": "image",
                    "payload": {
                        "url": media_url,
                        "is_reusable": True
                    }
                }
            }
            # Also send text if provided
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(url, params=params, json=payload)
                if text.strip():
                    text_payload = {
                        "recipient": {"id": recipient_id},
                        "messaging_type": "RESPONSE",
                        "message": {"text": text}
                    }
                    await client.post(url, params=params, json=text_payload)
                data = res.json()
                if res.status_code >= 400:
                    logger.error(f"Failed to send DM: {data}")
                return data

        payload["message"] = {"text": text}

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, params=params, json=payload)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Send DM error: {data}")
            return data

    async def send_private_reply(self, comment_id: str, text: str) -> Dict[str, Any]:
        """
        Sends a private reply DM to an Instagram user from a comment.
        Uses recipient: {"comment_id": comment_id}
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        url = f"{self.base_url}/{self.target_endpoint}/messages"
        params = {"access_token": self.access_token}
        payload = {
            "recipient": {"comment_id": comment_id},
            "message": {"text": text}
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, params=params, json=payload)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Private Reply error: {data}")
            return data

    async def get_user_profile(self, scoped_user_id: str) -> Dict[str, Any]:
        """
        Gets user profile including 'is_user_follow_business' for follow-gate check.
        Requires instagram_manage_messages scope.
        """
        if not self.access_token:
            return {"name": "User", "username": None, "is_user_follow_business": False}

        url = f"{self.base_url}/{scoped_user_id}"
        params = {
            "fields": "name,username,profile_pic,is_user_follow_business",
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    return res.json()
                else:
                    logger.warning(f"Failed to fetch profile for {scoped_user_id}: {res.text}")
                    return {"name": "User", "username": None, "is_user_follow_business": False}
        except Exception as e:
            logger.error(f"Exception fetching user profile: {e}")
            return {"name": "User", "username": None, "is_user_follow_business": False}

    async def set_ice_breakers(self, questions: list) -> Dict[str, Any]:
        """
        Sets conversation starter Ice Breakers (up to 4) on the Instagram profile.
        questions: list of dicts [{"question": "Get Price Guide", "payload": "GUIDE"}, ...]
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        url = f"{self.base_url}/me/messenger_profile"
        params = {"access_token": self.access_token}
        payload = {
            "platform": "instagram",
            "ice_breakers": questions
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await client.post(url, params=params, json=payload)
            return res.json()

    async def verify_connection(self) -> Dict[str, Any]:
        """
        Verifies if current PAGE_ACCESS_TOKEN and configuration are valid.
        """
        if not self.access_token:
            return {"status": "unconfigured", "message": "No PAGE_ACCESS_TOKEN set"}

        url = f"{self.base_url}/me"
        fields = "id,username,name" if self.access_token.startswith("IG") else "id,name"
        params = {
            "fields": fields,
            "access_token": self.access_token
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url, params=params)
                data = res.json()
                if res.status_code == 200:
                    return {
                        "status": "connected",
                        "page_id": data.get("id"),
                        "page_name": data.get("username") or data.get("name"),
                        "ig_account": {"id": self.ig_account_id} if self.ig_account_id else {}
                    }
                else:
                    return {
                        "status": "error",
                        "message": data.get("error", {}).get("message", "Unknown Meta API error")
                    }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# Singleton client instance
ig_client = InstagramGraphAPI()
