from datetime import datetime
from typing import Optional, List
from sqlmodel import SQLModel, Field, Column
import json

class AutomationRule(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(default="Keyword Rule")
    keywords: str = Field(default="[]")  # JSON string of list of keywords
    match_type: str = Field(default="contains")  # 'contains', 'exact', 'regex'
    rule_type: str = Field(default="all")  # 'all', 'dm', 'comment', 'story'
    response_text: str = Field(default="")
    response_media_url: Optional[str] = Field(default=None)
    target_media_id: Optional[str] = Field(default=None)  # scopes a 'comment' rule to one specific reel/post
    target_media_permalink: Optional[str] = Field(default=None)  # display label for the scoped reel/post
    public_reply_enabled: bool = Field(default=False)
    public_reply_text: Optional[str] = Field(default=None)
    follow_gate_enabled: bool = Field(default=False)
    follow_gate_message: str = Field(
        default="Hey there! 👋 Please follow our page first, then send the keyword again to unlock your exclusive access! 🎁"
    )
    cooldown_minutes: int = Field(default=1440)  # default 24h cooldown per user
    is_active: bool = Field(default=True)
    trigger_count: int = Field(default=0)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def get_keywords_list(self) -> List[str]:
        try:
            return json.loads(self.keywords)
        except Exception:
            return [k.strip() for k in self.keywords.split(",") if k.strip()]

    def set_keywords_list(self, kw_list: List[str]):
        self.keywords = json.dumps([k.strip().lower() for k in kw_list if k.strip()])


class ActionLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_type: str  # 'dm_received', 'comment_received', 'story_mention', 'dm_sent', 'private_reply_sent', 'public_reply_sent', 'follow_gate_blocked', 'queued_released', 'error'
    sender_id: str
    sender_username: Optional[str] = Field(default=None)
    rule_id: Optional[int] = Field(default=None)
    rule_name: Optional[str] = Field(default=None)
    status: str = Field(default="success")  # 'success', 'blocked', 'failed', 'info'
    details: str = Field(default="")


class QueuedDM(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: str
    sender_username: Optional[str] = Field(default=None)
    rule_id: int
    message_text: str
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    delivered: bool = Field(default=False)
    delivered_at: Optional[datetime] = Field(default=None)


class UserCooldown(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sender_id: str
    rule_id: int
    last_triggered_at: datetime = Field(default_factory=datetime.utcnow)


class AppConfig(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class ProcessedEvent(SQLModel, table=True):
    """Tracks webhook event IDs already handled, so Meta's at-least-once delivery
    (retries/redeliveries) can't trigger duplicate DMs for the same comment/message."""
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: str = Field(unique=True, index=True)
    event_type: str
    processed_at: datetime = Field(default_factory=datetime.utcnow)
