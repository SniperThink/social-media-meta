from fastapi import APIRouter, Request, HTTPException, Query
from app.models import schemas
from app.config import settings
import logging
import hmac
import hashlib
import json

router = APIRouter(prefix="/api/instagram", tags=["instagram_webhook"])

logger = logging.getLogger(__name__)


def verify_signature(request_body: bytes, signature: str) -> bool:
    """Verify the X-Hub-Signature-256 header for webhook authenticity."""
    if not settings.FACEBOOK_APP_SECRET:
        logger.warning("FACEBOOK_APP_SECRET not configured, skipping signature verification")
        return True

    expected_signature = hmac.new(
        settings.FACEBOOK_APP_SECRET.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected_signature}", signature)


@router.get("/webhook")
def verify_webhook(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token")
):
    """Verify webhook endpoint for Facebook/Instagram webhooks."""
    if hub_mode == "subscribe" and hub_verify_token == settings.FACEBOOK_WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verification successful")
        return hub_challenge
    else:
        logger.warning(f"Webhook verification failed: mode={hub_mode}, token={hub_verify_token}")
        raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def handle_webhook(request: Request):
    """Handle incoming Instagram webhook notifications."""
    # Get the signature for verification
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        logger.warning("No X-Hub-Signature-256 header provided")
        raise HTTPException(status_code=403, detail="Missing signature")

    # Read the raw body
    body = await request.body()

    # Verify signature
    if not verify_signature(body, signature):
        logger.warning("Invalid webhook signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse the JSON payload
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Failed to parse webhook payload as JSON")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Validate against schema
    try:
        webhook_data = schemas.InstagramWebhookRequest(**payload)
    except Exception as e:
        logger.error(f"Webhook payload validation failed: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload structure")

    # Process the webhook entries
    for entry in webhook_data.entry:
        logger.info(f"Processing webhook entry for Instagram account: {entry.id}")
        for change in entry.changes:
            field = change.get("field")
            value = change.get("value", {})

            if field == "media":
                # Handle media publication/update
                media_id = value.get("id") or value.get("media_id")
                permalink = value.get("permalink")
                caption = value.get("caption")
                timestamp = value.get("timestamp")
                logger.info(f"Media event: ID={media_id}, Permalink={permalink}, Caption={caption}, Timestamp={timestamp}")

                # TODO: Update DB with publication status if needed
                # For now, just log the event

            elif field == "comments":
                # Handle new comments
                comment_id = value.get("id") or value.get("comment_id")
                text = value.get("text")
                from_user = value.get("from", {}).get("username", "unknown")
                logger.info(f"Comment event: ID={comment_id}, Text={text}, From={from_user}")

                # TODO: Store comments or trigger responses

            else:
                # Handle other event types
                logger.info(f"Unhandled event type: {field}, Value: {value}")

    # Respond with 200 OK to acknowledge receipt
    return {"status": "ok"}
