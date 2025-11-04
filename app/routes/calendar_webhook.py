from fastapi import APIRouter, Request, HTTPException
from app.services.google_calender import handle_calendar_notification
import logging

router = APIRouter(prefix="/api/calendar", tags=["calendar"])

logger = logging.getLogger(__name__)

@router.post("/webhook")
async def calendar_webhook(request: Request):
    """Webhook endpoint to receive Google Calendar notifications for event changes/deletions."""
    try:
        # Google Calendar sends notifications as POST with headers containing metadata
        headers = dict(request.headers)
        logger.info(f"Calendar webhook headers: {headers}")

        # The notification body might be empty or contain minimal data
        body = await request.body()
        notification_data = {}

        if body:
            try:
                import json
                notification_data = json.loads(body)
            except json.JSONDecodeError:
                logger.warning("Failed to parse webhook body as JSON")

        # Add header information to notification data
        notification_data.update({
            'resourceId': headers.get('X-Goog-Resource-ID'),
            'resourceUri': headers.get('X-Goog-Resource-URI'),
            'channelId': headers.get('X-Goog-Channel-ID'),
            'messageNumber': headers.get('X-Goog-Message-Number'),
            'resourceState': headers.get('X-Goog-Resource-State'),  # 'exists', 'not_exists', etc.
        })

        # Handle the notification
        handle_calendar_notification(notification_data)

        # Respond with 200 OK to acknowledge receipt
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing calendar webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
