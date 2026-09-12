import hmac
import hashlib
import json
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from config import settings

logger = logging.getLogger("webhook_parser")

@dataclass
class ParsedEvent:
    event_type: str  # 'dm', 'comment', 'story_mention'
    sender_id: str
    sender_username: Optional[str]
    text: str
    raw_payload: Dict[str, Any]
    comment_id: Optional[str] = None
    media_id: Optional[str] = None
    story_url: Optional[str] = None
    timestamp: Optional[int] = None
    event_id: Optional[str] = None  # stable dedup key: message mid, or comment id

def verify_hub_token(mode: Optional[str], token: Optional[str]) -> bool:
    """Verifies the hub.mode and hub.verify_token during webhook registration."""
    return mode == "subscribe" and token == settings.META_VERIFY_TOKEN

def verify_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """
    Validates the X-Hub-Signature-256 header sent by Meta using the App Secret.
    If META_APP_SECRET is not configured or in debug mode, permits webhook.
    """
    if not settings.META_APP_SECRET or settings.DEBUG:
        return True

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected_hash = signature_header.split("sha256=")[1]
    computed_hash = hmac.new(
        key=settings.META_APP_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_hash, computed_hash)

def parse_webhook_payload(data: Dict[str, Any]) -> List[ParsedEvent]:
    """
    Parses incoming Meta Instagram webhook payload into normalized ParsedEvent objects.
    Handles:
    - Direct Messages ('messaging' entries)
    - Story mentions ('message.attachments' or story_share)
    - Post Comments ('changes' entries under 'comments')
    """
    events: List[ParsedEvent] = []

    obj_type = data.get("object")
    logger.info(f"Received webhook object type: {obj_type}")
    if obj_type not in ["instagram", "page"]:
        logger.warning(f"Ignoring unsupported webhook object: {obj_type}")
        return events

    for entry in data.get("entry", []):
        entry_time = entry.get("time")

        # 1. Check messaging array (Direct Messages, Story mentions, Quick Replies)
        if "messaging" in entry:
            for item in entry.get("messaging", []):
                sender = item.get("sender", {})
                sender_id = str(sender.get("id", ""))
                recipient = item.get("recipient", {})

                # Ignore echo messages sent by the bot itself
                if item.get("message", {}).get("is_echo"):
                    continue

                # Check if it's a standard text message or quick reply
                message = item.get("message", {})
                text = message.get("text", "")
                quick_reply = message.get("quick_reply", {})
                if quick_reply and "payload" in quick_reply:
                    text = quick_reply.get("payload", text)

                # Check attachments (for story mentions or shared media)
                attachments = message.get("attachments", [])
                story_url = None
                is_story_mention = False

                for att in attachments:
                    att_type = att.get("type")
                    if att_type in ["story_mention", "story_share"]:
                        is_story_mention = True
                        story_url = att.get("payload", {}).get("url")

                mid = message.get("mid")

                if is_story_mention:
                    events.append(ParsedEvent(
                        event_type="story_mention",
                        sender_id=sender_id,
                        sender_username=None,
                        text=text or "Story Mention",
                        story_url=story_url,
                        timestamp=entry_time,
                        raw_payload=item,
                        event_id=mid
                    ))
                elif text or message:
                    events.append(ParsedEvent(
                        event_type="dm",
                        sender_id=sender_id,
                        sender_username=None,
                        text=text.strip(),
                        timestamp=entry_time,
                        raw_payload=item,
                        event_id=mid
                    ))

        # 2. Check changes array (Comments on posts)
        if "changes" in entry:
            for change in entry.get("changes", []):
                field = change.get("field")
                value = change.get("value", {})

                if field == "comments":
                    sender = value.get("from", {})
                    sender_id = str(sender.get("id", ""))
                    sender_username = sender.get("username")
                    comment_id = str(value.get("id", ""))
                    media = value.get("media", {})
                    media_id = str(media.get("id", ""))
                    text = value.get("text", "")

                    events.append(ParsedEvent(
                        event_type="comment",
                        sender_id=sender_id,
                        sender_username=sender_username,
                        text=text.strip(),
                        comment_id=comment_id,
                        media_id=media_id,
                        timestamp=entry_time,
                        raw_payload=change,
                        event_id=comment_id
                    ))

    return events
