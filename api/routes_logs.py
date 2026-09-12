import asyncio
import json
from datetime import datetime, date
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Request
from sse_starlette.sse import EventSourceResponse
from sqlmodel import Session, select, func
from core.database import get_session
from core.models import ActionLog, AutomationRule, QueuedDM
from core.auth import get_current_user
from bot.handlers import subscribe_log_stream, unsubscribe_log_stream

router = APIRouter(prefix="/api", tags=["Logs & Stats"])

@router.get("/logs")
async def get_logs(
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    session: Session = Depends(get_session),
    user: str = Depends(get_current_user)
):
    statement = select(ActionLog).order_by(ActionLog.id.desc())
    if event_type:
        statement = statement.where(ActionLog.event_type == event_type)
    if status:
        statement = statement.where(ActionLog.status == status)

    statement = statement.offset(offset).limit(limit)
    logs = session.exec(statement).all()

    return [
        {
            "id": log.id,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "event_type": log.event_type,
            "sender_id": log.sender_id,
            "sender_username": log.sender_username,
            "rule_id": log.rule_id,
            "rule_name": log.rule_name,
            "status": log.status,
            "details": log.details
        }
        for log in logs
    ]

@router.delete("/logs")
async def clear_logs(session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    statement = select(ActionLog)
    logs = session.exec(statement).all()
    for l in logs:
        session.delete(l)
    session.commit()
    return {"message": "All activity logs cleared"}

@router.get("/stats")
async def get_dashboard_stats(session: Session = Depends(get_session), user: str = Depends(get_current_user)):
    # Total active rules
    active_rules = len(session.exec(select(AutomationRule).where(AutomationRule.is_active == True)).all())
    total_rules = len(session.exec(select(AutomationRule)).all())

    # Today's start
    today_midnight = datetime.combine(date.today(), datetime.min.time())

    # DMs sent today
    dms_today = len(session.exec(
        select(ActionLog).where(
            ActionLog.event_type.in_(["dm_sent", "private_reply_sent", "queued_released"]),
            ActionLog.timestamp >= today_midnight,
            ActionLog.status == "success"
        )
    ).all())

    # Follow gate blocks
    follow_gates_triggered = len(session.exec(
        select(ActionLog).where(
            ActionLog.event_type == "follow_gate_blocked"
        )
    ).all())

    # Queued pending
    pending_queued = len(session.exec(
        select(QueuedDM).where(QueuedDM.delivered == False)
    ).all())

    # Total lifetime triggers
    all_rules = session.exec(select(AutomationRule)).all()
    total_triggers = sum(r.trigger_count for r in all_rules)

    return {
        "active_rules": active_rules,
        "total_rules": total_rules,
        "dms_today": dms_today,
        "follow_gates_triggered": follow_gates_triggered,
        "pending_queued": pending_queued,
        "total_triggers": total_triggers
    }

@router.get("/logs/stream")
async def sse_logs_stream(request: Request):
    """
    Server-Sent Events (SSE) stream endpoint for live real-time log updates.
    Sends new logs to dashboard clients without polling.
    """
    q = subscribe_log_stream()

    async def event_generator():
        try:
            # Send initial ping
            yield {
                "event": "connected",
                "data": json.dumps({"message": "Connected to Instagram Auto live stream"})
            }
            while True:
                # Disconnect check
                if await request.is_disconnected():
                    break
                try:
                    # Wait for next broadcasted log with 20s heartbeat timeout
                    log_item = await asyncio.wait_for(q.get(), timeout=20.0)
                    yield {
                        "event": "log",
                        "data": json.dumps(log_item)
                    }
                except asyncio.TimeoutError:
                    # Send heartbeat ping to keep connection alive
                    yield {
                        "event": "ping",
                        "data": "keep-alive"
                    }
        finally:
            unsubscribe_log_stream(q)

    return EventSourceResponse(event_generator())
