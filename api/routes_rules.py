from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select
from typing import List, Optional
from pydantic import BaseModel
import json
from core.database import get_session
from core.models import AutomationRule
from core.auth import get_current_user

router = APIRouter(prefix="/api/rules", tags=["Rules"])

class RuleCreateUpdate(BaseModel):
    name: str
    keywords: List[str]
    match_type: str = "contains"  # 'contains', 'exact', 'regex'
    rule_type: str = "all"        # 'all', 'dm', 'comment', 'story'
    response_text: str
    response_media_url: Optional[str] = None
    target_media_id: Optional[str] = None
    target_media_permalink: Optional[str] = None
    public_reply_enabled: bool = False
    public_reply_text: Optional[str] = None
    follow_gate_enabled: bool = False
    follow_gate_message: Optional[str] = "Hey! Please follow our page first, then send the keyword again to get your link! 🚀"
    cooldown_minutes: int = 1440
    is_active: bool = True

def rule_to_dict(rule: AutomationRule) -> dict:
    return {
        "id": rule.id,
        "name": rule.name,
        "keywords": rule.get_keywords_list(),
        "match_type": rule.match_type,
        "rule_type": rule.rule_type,
        "response_text": rule.response_text,
        "response_media_url": rule.response_media_url,
        "target_media_id": rule.target_media_id,
        "target_media_permalink": rule.target_media_permalink,
        "public_reply_enabled": rule.public_reply_enabled,
        "public_reply_text": rule.public_reply_text,
        "follow_gate_enabled": rule.follow_gate_enabled,
        "follow_gate_message": rule.follow_gate_message,
        "cooldown_minutes": rule.cooldown_minutes,
        "is_active": rule.is_active,
        "trigger_count": rule.trigger_count,
        "created_at": rule.created_at.isoformat() if rule.created_at else None
    }

@router.get("")
async def list_rules(session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    rules = session.exec(select(AutomationRule).order_by(AutomationRule.id.desc())).all()
    return [rule_to_dict(r) for r in rules]

@router.post("")
async def create_rule(data: RuleCreateUpdate, session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    rule = AutomationRule(
        name=data.name,
        match_type=data.match_type,
        rule_type=data.rule_type,
        response_text=data.response_text,
        response_media_url=data.response_media_url,
        target_media_id=data.target_media_id,
        target_media_permalink=data.target_media_permalink,
        public_reply_enabled=data.public_reply_enabled,
        public_reply_text=data.public_reply_text,
        follow_gate_enabled=data.follow_gate_enabled,
        follow_gate_message=data.follow_gate_message or "Hey! Please follow our page first, then send the keyword again! 🚀",
        cooldown_minutes=data.cooldown_minutes,
        is_active=data.is_active
    )
    rule.set_keywords_list(data.keywords)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule_to_dict(rule)

@router.get("/{rule_id}")
async def get_rule(rule_id: int, session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    rule = session.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule_to_dict(rule)

@router.put("/{rule_id}")
async def update_rule(rule_id: int, data: RuleCreateUpdate, session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    rule = session.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    rule.name = data.name
    rule.set_keywords_list(data.keywords)
    rule.match_type = data.match_type
    rule.rule_type = data.rule_type
    rule.response_text = data.response_text
    rule.response_media_url = data.response_media_url
    rule.target_media_id = data.target_media_id
    rule.target_media_permalink = data.target_media_permalink
    rule.public_reply_enabled = data.public_reply_enabled
    rule.public_reply_text = data.public_reply_text
    rule.follow_gate_enabled = data.follow_gate_enabled
    if data.follow_gate_message:
        rule.follow_gate_message = data.follow_gate_message
    rule.cooldown_minutes = data.cooldown_minutes
    rule.is_active = data.is_active

    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule_to_dict(rule)

@router.delete("/{rule_id}")
async def delete_rule(rule_id: int, session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    rule = session.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    session.delete(rule)
    session.commit()
    return {"message": "Rule deleted successfully", "id": rule_id}

@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int, session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    rule = session.get(AutomationRule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_active = not rule.is_active
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return {"id": rule.id, "is_active": rule.is_active}
