import re
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlmodel import Session, select
from core.models import AutomationRule, UserCooldown, QueuedDM

class RuleEngine:
    @staticmethod
    def match_rule(text: str, event_type: str, session: Session, media_id: Optional[str] = None) -> Optional[AutomationRule]:
        """
        Finds the first active matching AutomationRule for the given input text and event type.
        Supported event_types: 'dm', 'comment', 'story'.
        Rule types: 'all', 'dm', 'comment', 'story'.

        Rules scoped to a specific reel/post (target_media_id) only apply when `media_id`
        matches, and are checked before global (unscoped) rules — so the same keyword can
        be mapped to a different resource per reel. Rules with no keywords act as a
        catch-all/fallback: they're only used if nothing else matched.
        """
        clean_text = text.strip().lower()

        # Query all active rules eligible for this event type and this specific media
        statement = select(AutomationRule).where(AutomationRule.is_active == True)
        rules = session.exec(statement).all()

        eligible = []
        for rule in rules:
            if rule.rule_type != "all" and rule.rule_type != event_type:
                continue
            if rule.target_media_id and rule.target_media_id != media_id:
                continue
            eligible.append(rule)

        # Media-scoped rules take priority over global (unscoped) rules
        eligible.sort(key=lambda r: 0 if r.target_media_id else 1)

        fallback: Optional[AutomationRule] = None
        for rule in eligible:
            keywords = rule.get_keywords_list()
            # If no keywords specified, this is a catch-all / fallback rule
            if not keywords:
                if fallback is None:
                    fallback = rule
                continue

            for kw in keywords:
                kw = kw.strip().lower()
                if not kw:
                    continue

                if rule.match_type == "exact":
                    if clean_text == kw:
                        return rule
                elif rule.match_type == "regex":
                    try:
                        if re.search(kw, clean_text, re.IGNORECASE):
                            return rule
                    except re.error:
                        pass
                else:  # Default: 'contains'
                    # Word boundary or substring contains
                    if kw in clean_text:
                        return rule

        return fallback

    @staticmethod
    def check_cooldown(sender_id: str, rule: AutomationRule, session: Session) -> bool:
        """
        Returns True if the user is in cooldown (should NOT be triggered again yet).
        Returns False if the user is eligible.
        """
        if rule.cooldown_minutes <= 0:
            return False

        statement = select(UserCooldown).where(
            UserCooldown.sender_id == sender_id,
            UserCooldown.rule_id == rule.id
        )
        record = session.exec(statement).first()

        if not record:
            return False

        cutoff = datetime.utcnow() - timedelta(minutes=rule.cooldown_minutes)
        if record.last_triggered_at > cutoff:
            return True  # still within cooldown period

        return False

    @staticmethod
    def update_cooldown(sender_id: str, rule_id: int, session: Session):
        """Updates or creates the user cooldown timestamp."""
        statement = select(UserCooldown).where(
            UserCooldown.sender_id == sender_id,
            UserCooldown.rule_id == rule_id
        )
        record = session.exec(statement).first()
        if record:
            record.last_triggered_at = datetime.utcnow()
            session.add(record)
        else:
            new_record = UserCooldown(
                sender_id=sender_id,
                rule_id=rule_id,
                last_triggered_at=datetime.utcnow()
            )
            session.add(new_record)
        session.commit()

    @staticmethod
    def queue_dm(sender_id: str, username: Optional[str], rule_id: int, message_text: str, session: Session) -> QueuedDM:
        """Saves a queued DM for a user who hasn't passed the follow gate yet."""
        queued = QueuedDM(
            sender_id=sender_id,
            sender_username=username,
            rule_id=rule_id,
            message_text=message_text,
            queued_at=datetime.utcnow(),
            delivered=False
        )
        session.add(queued)
        session.commit()
        session.refresh(queued)
        return queued

    @staticmethod
    def get_pending_queued(sender_id: str, session: Session) -> List[QueuedDM]:
        """Fetches pending undelivered queued DMs for this user."""
        statement = select(QueuedDM).where(
            QueuedDM.sender_id == sender_id,
            QueuedDM.delivered == False
        )
        return list(session.exec(statement).all())

    @staticmethod
    def mark_queued_delivered(queued: QueuedDM, session: Session):
        """Marks a queued DM as successfully delivered."""
        queued.delivered = True
        queued.delivered_at = datetime.utcnow()
        session.add(queued)
        session.commit()
