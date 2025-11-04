# app/services/google_calendar.py
import datetime
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.utils.auth import get_google_creds
import datetime as _dt
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import logging

logger = logging.getLogger(__name__)

def create_calendar_event(scheduled_time_str: str, caption: str, drive_folder_id: str, post_type: str, timezone: str = None):
    """Creates a Google Calendar event for the scheduled post."""
    creds = get_google_creds()
    try:
        service = build("calendar", "v3", credentials=creds)
        # Parse the datetime string robustly. Accepts ISO strings with offsets or 'Z'.
        # If the incoming datetime is naive (no tzinfo), assume IST (UTC+5:30) per user preference.
        # Keep in user's timezone for Google Calendar to display correctly.
        ts = scheduled_time_str
        if ts.endswith('Z'):
            ts = ts.replace('Z', '+00:00')

        try:
            scheduled_time = _dt.datetime.fromisoformat(ts)
        except Exception:
            # Fallback: try to parse without microseconds
            scheduled_time = _dt.datetime.fromisoformat(ts.split('.')[0])

        # Determine the target timezone
        if timezone:
            tz_name = timezone
            try:
                if ZoneInfo:
                    tz = ZoneInfo(timezone)
                else:
                    tz = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
            except Exception:
                tz = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
                tz_name = 'Asia/Kolkata'
        else:
            tz = _dt.timezone(_dt.timedelta(hours=5, minutes=30))
            tz_name = 'Asia/Kolkata'

        # If naive, assume it's in the target timezone
        if scheduled_time.tzinfo is None:
            scheduled_time = scheduled_time.replace(tzinfo=tz)
        else:
            # If it has tzinfo (e.g., UTC from 'Z'), convert to target timezone
            scheduled_time = scheduled_time.astimezone(tz)

        end_time = scheduled_time + _dt.timedelta(minutes=30)

        drive_folder_link = f"https://drive.google.com/drive/folders/{drive_folder_id}"

        event = {
            "summary": f"Scheduled Post: {post_type.title()}",
            "description": f"**Caption:**\n{caption}\n\n**Assets Link:**\n{drive_folder_link}",
            "start": {
                "dateTime": scheduled_time.isoformat(),
                "timeZone": tz_name,
            },
            "end": {
                "dateTime": end_time.isoformat(),
                "timeZone": tz_name,
            },
        }

        event = (
            service.events()
            .insert(calendarId="primary", body=event)
            .execute()
        )
        print(f"Event created: {event.get('htmlLink')}")
        return event.get('id')

    except HttpError as error:
        print(f"An error occurred during GCalendar creation: {error}")
        raise


def setup_calendar_watch(calendar_id: str = "primary", webhook_url: str = None):
    """Sets up a watch channel for calendar events to detect deletions."""
    creds = get_google_creds()
    try:
        service = build("calendar", "v3", credentials=creds)

        if not webhook_url:
            from app.config import settings
            webhook_url = settings.CALENDAR_WEBHOOK_URL or "https://your-app.com/api/calendar/webhook"

        # Create a unique channel ID
        import uuid
        channel_id = str(uuid.uuid4())

        body = {
            "id": channel_id,
            "type": "web_hook",
            "address": webhook_url,
            "params": {
                "ttl": "86400"  # 24 hours
            }
        }

        response = service.events().watch(calendarId=calendar_id, body=body).execute()
        logger.info(f"Calendar watch channel created: {response}")
        return response

    except HttpError as error:
        logger.error(f"An error occurred setting up calendar watch: {error}")
        raise


def handle_calendar_notification(notification_data: dict):
    """Handles incoming calendar notifications for event changes/deletions."""
    logger.info(f"Received calendar notification: {notification_data}")

    # Extract event ID from the notification
    event_id = notification_data.get('resourceId')  # This might be the event ID or channel ID

    # For deletions, the notification might indicate the event was removed
    # We need to check if the event still exists or if it's been deleted
    creds = get_google_creds()
    try:
        service = build("calendar", "v3", credentials=creds)

        # Try to get the event
        try:
            event = service.events().get(calendarId="primary", eventId=event_id).execute()
            logger.info(f"Event {event_id} still exists: {event.get('summary')}")
            # Event exists, perhaps updated - handle accordingly
        except HttpError as e:
            if e.resp.status == 404:
                logger.info(f"Event {event_id} has been deleted")
                # Mark the corresponding post as cancelled
                from app.database import crud
                crud.cancel_post_by_event_id(event_id)
            else:
                logger.error(f"Error fetching event {event_id}: {e}")

    except Exception as e:
        logger.error(f"Error handling calendar notification: {e}")
