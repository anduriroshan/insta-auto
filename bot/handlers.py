import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlmodel import Session
from core.models import ActionLog, AutomationRule, QueuedDM
from bot.webhook import ParsedEvent
from bot.instagram import ig_client
from bot.rules import RuleEngine

logger = logging.getLogger("event_handlers")

# Real-time SSE broadcaster queue list
_sse_subscribers: List[asyncio.Queue] = []

def subscribe_log_stream() -> asyncio.Queue:
    q = asyncio.Queue(maxsize=100)
    _sse_subscribers.append(q)
    return q

def unsubscribe_log_stream(q: asyncio.Queue):
    if q in _sse_subscribers:
        _sse_subscribers.remove(q)

async def broadcast_log(log_data: Dict[str, Any]):
    """Broadcasts a real-time event to all connected dashboard SSE clients."""
    for q in list(_sse_subscribers):
        try:
            q.put_nowait(log_data)
        except (asyncio.QueueFull, Exception):
            pass

def create_and_broadcast_log(
    session: Session,
    event_type: str,
    sender_id: str,
    status: str,
    details: str,
    sender_username: Optional[str] = None,
    rule_id: Optional[int] = None,
    rule_name: Optional[str] = None
) -> ActionLog:
    """Saves action to DB and notifies all active dashboard clients."""
    log = ActionLog(
        timestamp=datetime.utcnow(),
        event_type=event_type,
        sender_id=sender_id,
        sender_username=sender_username,
        rule_id=rule_id,
        rule_name=rule_name,
        status=status,
        details=details
    )
    session.add(log)
    session.commit()
    session.refresh(log)

    log_dict = {
        "id": log.id,
        "timestamp": log.timestamp.isoformat(),
        "event_type": log.event_type,
        "sender_id": log.sender_id,
        "sender_username": log.sender_username or "Instagram User",
        "rule_id": log.rule_id,
        "rule_name": log.rule_name,
        "status": log.status,
        "details": log.details
    }
    
    # Broadcast asynchronously
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(broadcast_log(log_dict))
    except RuntimeError:
        pass

    return log


class EventHandler:

    # ── Quick Reply Payload Prefixes ──
    PAYLOAD_SEND_LINK = "SEND_LINK_RULE_"      # User tapped "Send me the link"
    PAYLOAD_CHECK_FOLLOW = "CHECK_FOLLOW_RULE_" # User tapped "I'm following! ✅"

    @staticmethod
    async def handle_dm(event: ParsedEvent, session: Session):
        """Processes incoming direct message, including Quick Reply button taps."""
        logger.info(f"Incoming DM from {event.sender_id}: {event.text}")

        text = event.text or ""

        # ─── Handle Quick Reply: "Send me the link ✨" ───
        if text.startswith(EventHandler.PAYLOAD_SEND_LINK):
            rule_id_str = text[len(EventHandler.PAYLOAD_SEND_LINK):]
            await EventHandler._handle_send_link_tap(event.sender_id, rule_id_str, session)
            return

        # ─── Handle Quick Reply: "I'm following! ✅" ───
        if text.startswith(EventHandler.PAYLOAD_CHECK_FOLLOW):
            rule_id_str = text[len(EventHandler.PAYLOAD_CHECK_FOLLOW):]
            await EventHandler._handle_follow_check_tap(event.sender_id, rule_id_str, session)
            return

        # ─── Legacy: Check if this user has pending queued DMs (from old text-based flow) ───
        pending_queued = RuleEngine.get_pending_queued(event.sender_id, session)
        if pending_queued:
            profile = await ig_client.get_user_profile(event.sender_id)
            is_following = profile.get("is_user_follow_business", False)
            username = profile.get("username")

            if is_following:
                for item in pending_queued:
                    await ig_client.send_dm(event.sender_id, item.message_text)
                    RuleEngine.mark_queued_delivered(item, session)
                    create_and_broadcast_log(
                        session=session,
                        event_type="queued_released",
                        sender_id=event.sender_id,
                        sender_username=username,
                        rule_id=item.rule_id,
                        status="success",
                        details=f"Follow detected! Released queued DM to @{username or event.sender_id}"
                    )
                return

        # ─── Standard keyword-matched DM auto-reply ───
        rule = RuleEngine.match_rule(event.text, "dm", session)
        if not rule:
            logger.info(f"No rule matched for DM text: {event.text}")
            return

        if RuleEngine.check_cooldown(event.sender_id, rule, session):
            logger.info(f"User {event.sender_id} is in cooldown for rule '{rule.name}'")
            create_and_broadcast_log(
                session=session,
                event_type="dm_received",
                sender_id=event.sender_id,
                rule_id=rule.id,
                rule_name=rule.name,
                status="info",
                details=f"Ignored trigger '{event.text}' due to active cooldown ({rule.cooldown_minutes}m)"
            )
            return

        # If follow gate is enabled on a DM rule, use the interactive button flow
        if rule.follow_gate_enabled:
            profile = await ig_client.get_user_profile(event.sender_id)
            is_following = profile.get("is_user_follow_business", False)
            username = profile.get("username")

            if not is_following:
                await EventHandler._send_follow_gate_buttons(event.sender_id, rule, username, session)
                return

        # Send Auto-Reply
        result = await ig_client.send_dm(
            recipient_id=event.sender_id,
            text=rule.response_text,
            media_url=rule.response_media_url
        )

        RuleEngine.update_cooldown(event.sender_id, rule.id, session)
        rule.trigger_count += 1
        session.add(rule)
        session.commit()

        status_str = "success" if not result.get("error") else "failed"
        details_str = f"Auto-replied to keyword '{event.text}' with rule '{rule.name}'"
        if result.get("error"):
            details_str = f"Meta Send Error: {result.get('error', {}).get('message')}"

        create_and_broadcast_log(
            session=session,
            event_type="dm_sent",
            sender_id=event.sender_id,
            rule_id=rule.id,
            rule_name=rule.name,
            status=status_str,
            details=details_str
        )

    @staticmethod
    async def handle_comment(event: ParsedEvent, session: Session):
        """Processes incoming comment — sends DM with interactive Quick Reply button."""
        logger.info(f"Incoming comment from @{event.sender_username}: {event.text}")

        rule = RuleEngine.match_rule(event.text, "comment", session, media_id=event.media_id)
        if not rule:
            logger.info(f"No rule matched for comment: {event.text}")
            return

        if RuleEngine.check_cooldown(event.sender_id, rule, session):
            logger.info(f"User {event.sender_id} in cooldown for comment rule '{rule.name}'")
            return

        # ── Send DM with "Send me the link" Quick Reply button ──
        greeting = (
            f"Hey there! 👋 Thanks for commenting on our post!\n\n"
            f"Tap the button below to get your resource 🎁"
        )
        quick_replies = [
            {
                "content_type": "text",
                "title": "Send me the link ✨",
                "payload": f"{EventHandler.PAYLOAD_SEND_LINK}{rule.id}"
            }
        ]

        result = await ig_client.send_private_reply_with_quick_replies(
            comment_id=event.comment_id,
            text=greeting,
            quick_replies=quick_replies
        )

        # If quick replies failed (API limitation), fall back to plain private reply
        if result.get("error"):
            logger.warning(f"Quick reply failed, falling back to plain DM: {result}")
            result = await ig_client.send_private_reply(event.comment_id, greeting)

        RuleEngine.update_cooldown(event.sender_id, rule.id, session)
        rule.trigger_count += 1
        session.add(rule)
        session.commit()

        status_str = "success" if not result.get("error") else "failed"
        details_str = f"Interactive DM sent to @{event.sender_username or event.sender_id} for comment '{event.text}'"
        if result.get("error"):
            details_str = f"Meta Private Reply Error: {result.get('error', {}).get('message')}"

        create_and_broadcast_log(
            session=session,
            event_type="private_reply_sent",
            sender_id=event.sender_id,
            sender_username=event.sender_username,
            rule_id=rule.id,
            rule_name=rule.name,
            status=status_str,
            details=details_str
        )

        # Optional public reply (social proof)
        if rule.public_reply_enabled and rule.public_reply_text:
            public_result = await ig_client.reply_to_comment(event.comment_id, rule.public_reply_text)
            public_status = "success" if not public_result.get("error") else "failed"
            public_details = f"Public reply posted for comment '{event.text}'"
            if public_result.get("error"):
                public_details = f"Meta Public Reply Error: {public_result.get('error', {}).get('message')}"

            create_and_broadcast_log(
                session=session,
                event_type="public_reply_sent",
                sender_id=event.sender_id,
                sender_username=event.sender_username,
                rule_id=rule.id,
                rule_name=rule.name,
                status=public_status,
                details=public_details
            )

    @staticmethod
    async def _handle_send_link_tap(sender_id: str, rule_id_str: str, session: Session):
        """
        User tapped "Send me the link ✨" — check follow status:
        - Following → deliver the resource immediately
        - Not following → send follow-gate with "I'm following! ✅" button
        """
        try:
            rule_id = int(rule_id_str)
        except ValueError:
            logger.error(f"Invalid rule ID from quick reply payload: {rule_id_str}")
            return

        rule = session.get(AutomationRule, rule_id)
        if not rule:
            logger.error(f"Rule {rule_id} not found for send_link tap")
            await ig_client.send_dm(sender_id, "Oops! This resource is no longer available. 😅")
            return

        profile = await ig_client.get_user_profile(sender_id)
        is_following = profile.get("is_user_follow_business", False)
        username = profile.get("username")

        if is_following or not rule.follow_gate_enabled:
            # ✅ User is following (or no gate) → deliver the resource
            result = await ig_client.send_dm(
                recipient_id=sender_id,
                text=rule.response_text,
                media_url=rule.response_media_url
            )
            status_str = "success" if not result.get("error") else "failed"
            create_and_broadcast_log(
                session=session,
                event_type="dm_sent",
                sender_id=sender_id,
                sender_username=username,
                rule_id=rule.id,
                rule_name=rule.name,
                status=status_str,
                details=f"Resource delivered to @{username or sender_id} via button tap"
            )
        else:
            # ❌ Not following → send follow-gate with interactive button
            await EventHandler._send_follow_gate_buttons(sender_id, rule, username, session)

    @staticmethod
    async def _handle_follow_check_tap(sender_id: str, rule_id_str: str, session: Session):
        """
        User tapped "I'm following! ✅" — re-check follow status:
        - Following → release queued resource
        - Still not following → prompt again with button
        """
        try:
            rule_id = int(rule_id_str)
        except ValueError:
            logger.error(f"Invalid rule ID from follow check payload: {rule_id_str}")
            return

        rule = session.get(AutomationRule, rule_id)
        if not rule:
            logger.error(f"Rule {rule_id} not found for follow_check tap")
            await ig_client.send_dm(sender_id, "Oops! This resource is no longer available. 😅")
            return

        profile = await ig_client.get_user_profile(sender_id)
        is_following = profile.get("is_user_follow_business", False)
        username = profile.get("username")

        if is_following:
            # ✅ Now following! Deliver the resource + release any queued DMs
            result = await ig_client.send_dm(
                recipient_id=sender_id,
                text=f"🎉 Thank you for following, @{username or 'friend'}! Here's your resource:\n\n{rule.response_text}",
                media_url=rule.response_media_url
            )

            # Also release any pending queued DMs for this user
            pending = RuleEngine.get_pending_queued(sender_id, session)
            for item in pending:
                if item.rule_id == rule.id:
                    RuleEngine.mark_queued_delivered(item, session)

            create_and_broadcast_log(
                session=session,
                event_type="queued_released",
                sender_id=sender_id,
                sender_username=username,
                rule_id=rule.id,
                rule_name=rule.name,
                status="success",
                details=f"Follow confirmed via button! Resource delivered to @{username or sender_id}"
            )
        else:
            # ❌ Still not following — re-send the follow gate prompt with button
            not_yet_msg = (
                f"Hmm, it looks like you haven't followed us yet! 😅\n\n"
                f"Please follow @thatswhatdatasaid and tap the button again 👇"
            )
            quick_replies = [
                {
                    "content_type": "text",
                    "title": "I'm following! ✅",
                    "payload": f"{EventHandler.PAYLOAD_CHECK_FOLLOW}{rule.id}"
                }
            ]
            await ig_client.send_dm_with_quick_replies(sender_id, not_yet_msg, quick_replies)

            create_and_broadcast_log(
                session=session,
                event_type="follow_gate_blocked",
                sender_id=sender_id,
                sender_username=username,
                rule_id=rule.id,
                rule_name=rule.name,
                status="blocked",
                details=f"Follow re-check failed for @{username or sender_id}. Prompted again."
            )

    @staticmethod
    async def _send_follow_gate_buttons(sender_id: str, rule: AutomationRule, username: Optional[str], session: Session):
        """
        Sends the follow-gate prompt with an interactive "I'm following! ✅" Quick Reply button,
        and queues the resource for delivery once they follow.
        """
        gate_msg = rule.follow_gate_message or (
            "Hey there! 👋 To get this exclusive resource, "
            "please follow our page first!\n\n"
            "Once you've followed, tap the button below 👇"
        )
        quick_replies = [
            {
                "content_type": "text",
                "title": "I'm following! ✅",
                "payload": f"{EventHandler.PAYLOAD_CHECK_FOLLOW}{rule.id}"
            }
        ]

        await ig_client.send_dm_with_quick_replies(sender_id, gate_msg, quick_replies)

        # Queue the resource so it gets delivered once they follow
        RuleEngine.queue_dm(
            sender_id=sender_id,
            username=username,
            rule_id=rule.id,
            message_text=rule.response_text,
            session=session
        )

        create_and_broadcast_log(
            session=session,
            event_type="follow_gate_blocked",
            sender_id=sender_id,
            sender_username=username,
            rule_id=rule.id,
            rule_name=rule.name,
            status="blocked",
            details=f"Follow gate with button sent to @{username or sender_id}. Resource queued."
        )

    @staticmethod
    async def handle_story_mention(event: ParsedEvent, session: Session):
        """Processes incoming story mention."""
        logger.info(f"Incoming story mention from {event.sender_id}")

        rule = RuleEngine.match_rule(event.text or "story", "story", session)
        reply_text = rule.response_text if rule else "Thank you so much for mentioning us in your Story! ❤️✨ We truly appreciate your support!"
        rule_id = rule.id if rule else None
        rule_name = rule.name if rule else "Default Story Thank You"

        result = await ig_client.send_dm(event.sender_id, reply_text)

        if rule:
            rule.trigger_count += 1
            session.add(rule)
            session.commit()

        status_str = "success" if not result.get("error") else "failed"
        create_and_broadcast_log(
            session=session,
            event_type="story_mention",
            sender_id=event.sender_id,
            rule_id=rule_id,
            rule_name=rule_name,
            status=status_str,
            details=f"Auto-sent thank-you DM for Story mention"
        )

