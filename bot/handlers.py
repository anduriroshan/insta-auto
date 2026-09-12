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
    @staticmethod
    async def handle_dm(event: ParsedEvent, session: Session):
        """Processes incoming direct message."""
        logger.info(f"Incoming DM from {event.sender_id}: {event.text}")

        # 1. First, check if this user has pending queued DMs from a previous follow-gate check
        pending_queued = RuleEngine.get_pending_queued(event.sender_id, session)
        if pending_queued:
            # Check if user now follows
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

        # 2. Match message against automation rules
        rule = RuleEngine.match_rule(event.text, "dm", session)
        if not rule:
            logger.info(f"No rule matched for DM text: {event.text}")
            return

        # 3. Check Cooldown
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

        # 4. Handle Follow-Gate if enabled
        if rule.follow_gate_enabled:
            profile = await ig_client.get_user_profile(event.sender_id)
            is_following = profile.get("is_user_follow_business", False)
            username = profile.get("username")

            if not is_following:
                # Send the follow gate prompt message
                await ig_client.send_dm(event.sender_id, rule.follow_gate_message)
                # Queue the reward delivery
                RuleEngine.queue_dm(
                    sender_id=event.sender_id,
                    username=username,
                    rule_id=rule.id,
                    message_text=rule.response_text,
                    session=session
                )
                create_and_broadcast_log(
                    session=session,
                    event_type="follow_gate_blocked",
                    sender_id=event.sender_id,
                    sender_username=username,
                    rule_id=rule.id,
                    rule_name=rule.name,
                    status="blocked",
                    details=f"Follow gate prompt sent to @{username or event.sender_id}. Resource queued."
                )
                return

        # 5. Send Auto-Reply
        result = await ig_client.send_dm(
            recipient_id=event.sender_id,
            text=rule.response_text,
            media_url=rule.response_media_url
        )

        # Update cooldown & stats
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
        """Processes incoming comment on a post/reel."""
        logger.info(f"Incoming comment from @{event.sender_username}: {event.text}")

        rule = RuleEngine.match_rule(event.text, "comment", session)
        if not rule:
            logger.info(f"No rule matched for comment: {event.text}")
            return

        if RuleEngine.check_cooldown(event.sender_id, rule, session):
            logger.info(f"User {event.sender_id} in cooldown for comment rule '{rule.name}'")
            return

        # Send private reply DM using comment_id
        result = await ig_client.send_private_reply(event.comment_id, rule.response_text)

        RuleEngine.update_cooldown(event.sender_id, rule.id, session)
        rule.trigger_count += 1
        session.add(rule)
        session.commit()

        status_str = "success" if not result.get("error") else "failed"
        details_str = f"Private reply DM sent to @{event.sender_username or event.sender_id} for comment '{event.text}'"
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
