import logging
from fastapi import APIRouter, Request, Response, HTTPException, Depends
from sqlmodel import Session
from sqlalchemy.exc import IntegrityError
from config import settings
from core.database import get_session
from core.models import ProcessedEvent
from bot.webhook import verify_hub_token, verify_signature, parse_webhook_payload
from bot.handlers import EventHandler, create_and_broadcast_log

router = APIRouter(tags=["Webhook"])
logger = logging.getLogger("routes_webhook")

@router.get("/webhook")
async def meta_webhook_verification(request: Request):
    """
    Meta Developer Dashboard sends a GET request to verify the webhook endpoint.
    Expects hub.mode=subscribe, hub.verify_token=<token>, and hub.challenge=<number>.
    Must return the hub.challenge as plain text.
    """
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    logger.info(f"Received Meta webhook verification handshake: mode={mode}, token_matches={token == settings.META_VERIFY_TOKEN}")

    if verify_hub_token(mode, token):
        logger.info("Webhook verification SUCCESS! Returning challenge.")
        return Response(content=challenge, media_type="text/plain")

    logger.warning("Webhook verification FAILED: Invalid token or mode.")
    raise HTTPException(status_code=403, detail="Verification token mismatch")


@router.post("/webhook")
@router.post("/")
async def meta_webhook_events(request: Request, session: Session = Depends(get_session)):
    """
    Meta sends real-time Instagram events (DMs, comments, story mentions) via POST.
    Validates X-Hub-Signature-256 header and immediately processes events.
    Returns 200 OK to acknowledge receipt.
    """
    raw_body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    # Validate HMAC signature if App Secret is configured
    if not verify_signature(raw_body, signature):
        if settings.DEBUG:
            logger.warning(f"Signature verification mismatch, but continuing in DEBUG mode.")
        else:
            logger.warning("Rejecting webhook POST: Invalid X-Hub-Signature-256")
            raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to decode JSON from webhook: {e}")
        return Response(content="EVENT_RECEIVED", status_code=200)

    events = parse_webhook_payload(payload)
    logger.info(f"Parsed {len(events)} events from webhook")

    for event in events:
        try:
            # Meta delivers webhooks at-least-once and will redeliver on timeout/retry.
            # Record the event id up front so a redelivered comment/message can't trigger
            # a duplicate DM or public reply.
            if event.event_id:
                try:
                    session.add(ProcessedEvent(event_id=event.event_id, event_type=event.event_type))
                    session.commit()
                except IntegrityError:
                    session.rollback()
                    logger.info(f"Skipping duplicate webhook event: {event.event_id}")
                    continue

            if event.event_type == "dm":
                await EventHandler.handle_dm(event, session)
            elif event.event_type == "comment":
                await EventHandler.handle_comment(event, session)
            elif event.event_type == "story_mention":
                await EventHandler.handle_story_mention(event, session)
        except Exception as e:
            logger.error(f"Error handling event {event.event_type}: {e}", exc_info=True)
            create_and_broadcast_log(
                session=session,
                event_type="error",
                sender_id=event.sender_id,
                status="failed",
                details=f"Error in {event.event_type}: {str(e)}"
            )

    # Always return 200 to Meta
    return Response(content="EVENT_RECEIVED", status_code=200)
