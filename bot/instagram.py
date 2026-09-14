import asyncio
import httpx
import logging
from typing import Optional, Dict, Any, List
from config import settings

logger = logging.getLogger("instagram_api")

class InstagramGraphAPI:
    def __init__(self, page_access_token: Optional[str] = None, ig_account_id: Optional[str] = None):
        self.access_token = page_access_token or settings.PAGE_ACCESS_TOKEN
        self.ig_account_id = ig_account_id or settings.INSTAGRAM_ACCOUNT_ID
        self.page_id = settings.PAGE_ID

    async def _request_with_retry(self, client: httpx.AsyncClient, method: str, url: str, max_retries: int = 3, **kwargs) -> httpx.Response:
        """
        Runs an HTTP request with exponential backoff on network errors, rate limiting (429),
        and transient 5xx errors from the Graph API. A viral reel can burst far more comments
        through than a single request budget, so retrying here avoids silently dropped sends.
        """
        delay = 0.5
        res: Optional[httpx.Response] = None
        for attempt in range(max_retries):
            try:
                res = await client.request(method, url, **kwargs)
            except httpx.RequestError as e:
                if attempt == max_retries - 1:
                    raise
                logger.warning(f"Graph API request error ({e}), retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 3
                continue

            if res.status_code == 429 or res.status_code >= 500:
                if attempt == max_retries - 1:
                    return res
                logger.warning(f"Graph API returned {res.status_code}, retrying in {delay}s...")
                await asyncio.sleep(delay)
                delay *= 3
                continue

            return res
        return res

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
                res = await self._request_with_retry(client, "POST", url, params=params, json=payload)
                if text.strip():
                    text_payload = {
                        "recipient": {"id": recipient_id},
                        "messaging_type": "RESPONSE",
                        "message": {"text": text}
                    }
                    await self._request_with_retry(client, "POST", url, params=params, json=text_payload)
                data = res.json()
                if res.status_code >= 400:
                    logger.error(f"Failed to send DM: {data}")
                return data

        payload["message"] = {"text": text}

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await self._request_with_retry(client, "POST", url, params=params, json=payload)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Send DM error: {data}")
            return data

    async def send_dm_with_quick_replies(
        self, recipient_id: str, text: str, quick_replies: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Sends a DM with Quick Reply buttons (tappable chips below the message).
        quick_replies: list of dicts with keys 'content_type', 'title', 'payload'.
        Example: [{"content_type": "text", "title": "Send me the link ✨", "payload": "SEND_LINK_RULE_1"}]
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        url = f"{self.base_url}/{self.target_endpoint}/messages"
        params = {"access_token": self.access_token}
        payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {
                "text": text,
                "quick_replies": quick_replies
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await self._request_with_retry(client, "POST", url, params=params, json=payload)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Quick Reply DM error: {data}")
            return data

    async def send_private_reply_with_quick_replies(
        self, comment_id: str, text: str, quick_replies: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """
        Sends a private reply DM (triggered from a comment) with Quick Reply buttons.
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        url = f"{self.base_url}/{self.target_endpoint}/messages"
        params = {"access_token": self.access_token}
        payload = {
            "recipient": {"comment_id": comment_id},
            "message": {
                "text": text,
                "quick_replies": quick_replies
            }
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await self._request_with_retry(client, "POST", url, params=params, json=payload)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Private Reply Quick Reply error: {data}")
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
            res = await self._request_with_retry(client, "POST", url, params=params, json=payload)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Private Reply error: {data}")
            return data

    async def reply_to_comment(self, comment_id: str, text: str) -> Dict[str, Any]:
        """
        Publicly replies to a comment (visible to everyone under the reel/post), as opposed
        to send_private_reply which sends a DM. Uses POST /{comment_id}/replies.
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        url = f"{self.base_url}/{comment_id}/replies"
        params = {"access_token": self.access_token, "message": text}

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await self._request_with_retry(client, "POST", url, params=params)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Meta Public Reply error: {data}")
            return data

    async def get_recent_media(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fetches recent posts/reels from the connected IG account so a rule can be scoped
        to one specific piece of content (e.g. different resources per reel).
        """
        if not self.access_token:
            raise ValueError("PAGE_ACCESS_TOKEN is not configured.")

        is_ig_token = self.access_token.startswith("IG")
        if is_ig_token:
            url = f"{self.base_url}/me/media"
        else:
            if not self.ig_account_id:
                raise ValueError("INSTAGRAM_ACCOUNT_ID is not configured.")
            url = f"{self.base_url}/{self.ig_account_id}/media"

        params = {
            "fields": "id,caption,media_type,media_url,permalink,thumbnail_url,timestamp",
            "limit": limit,
            "access_token": self.access_token
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            res = await self._request_with_retry(client, "GET", url, params=params)
            data = res.json()
            if res.status_code >= 400:
                logger.error(f"Failed to fetch recent media: {data}")
                raise ValueError(data.get("error", {}).get("message", "Failed to fetch recent media"))
            return data.get("data", [])

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
                res = await self._request_with_retry(client, "GET", url, params=params)
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
            res = await self._request_with_retry(client, "POST", url, params=params, json=payload)
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
                res = await self._request_with_retry(client, "GET", url, params=params)
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
