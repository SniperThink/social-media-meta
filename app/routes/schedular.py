# app/routes/scheduler.py
from fastapi import APIRouter, HTTPException
from app.models import schemas
from app.services import google_drive, google_calender, publisher_service, r2_service
from app.database import crud
from app.utils.retry import retry
import requests
import tempfile
import os
import uuid
from typing import Dict
from io import BytesIO
from PIL import Image
from app.config import settings

router = APIRouter(
    prefix="/api/schedule",
    tags=["Scheduling"]
)

@router.post("/", response_model=schemas.ScheduleResponse)
async def schedule_post(req: schemas.ScheduleRequest):
    """
    Receives selected content and schedule, uploads to GDrive,
    creates GCalendar event, and saves to DB.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"📅 Received schedule request for {req.post_type} at {req.scheduled_time}")

    try:
        # 1. Upload selected files to Google Drive (now returns folder_id and uploaded_media metadata)
        drive_upload_success = False
        drive_error_message = None
        folder_id = None
        uploaded_media = None

        try:
            folder_id, uploaded_media = google_drive.upload_files_to_drive(
                req.selected_media,  # These are now file paths or URLs
                req.selected_caption,
                req.post_type
            )
            if folder_id and uploaded_media is not None:
                drive_upload_success = True
                logger.info(f"✅ Drive upload successful: folder_id={folder_id}, media_count={len(uploaded_media)}")
            else:
                drive_error_message = "Drive upload returned invalid data"
                logger.warning(f"⚠️ Drive upload failed: {drive_error_message}")
        except Exception as drive_e:
            drive_error_message = str(drive_e)
            logger.error(f"❌ Drive upload error: {drive_error_message}")
            # Check if it's a storage quota error
            if "quota" in drive_error_message.lower() or "storage" in drive_error_message.lower() or "full" in drive_error_message.lower():
                logger.warning("   → Detected Drive storage quota issue - continuing with scheduling")
            else:
                logger.warning("   → Drive upload failed for other reasons - continuing with scheduling")

        # 2. Create Google Calendar event (only if Drive upload succeeded, otherwise use fallback)
        event_id = None
        calendar_error_message = None

        if drive_upload_success and folder_id:
            try:
                event_id = google_calender.create_calendar_event(
                    req.scheduled_time,
                    req.selected_caption,
                    folder_id,
                    req.post_type,
                    timezone=(req.timezone if hasattr(req, 'timezone') else None)
                )
                if event_id:
                    logger.info(f"✅ Calendar event created: {event_id}")
                else:
                    calendar_error_message = "Calendar event creation returned no event_id"
                    logger.warning(f"⚠️ Calendar event creation failed: {calendar_error_message}")
            except Exception as cal_e:
                calendar_error_message = str(cal_e)
                logger.error(f"❌ Calendar event creation error: {calendar_error_message}")
        else:
            calendar_error_message = "Skipped calendar event creation due to Drive upload failure"
            logger.warning(f"⚠️ {calendar_error_message}")

        # 3. Save record to the configured database (store uploaded media metadata, not local temp paths)
        db_save_success = False
        db_error_message = None

        try:
            # Use fallback values if Drive upload failed
            final_folder_id = folder_id or f"no_drive_{req.post_type}_{req.scheduled_time.replace(':', '-').replace('T', '_')}"
            final_event_id = event_id or f"no_calendar_{req.post_type}_{req.scheduled_time.replace(':', '-').replace('T', '_')}"
            final_uploaded_media = uploaded_media or []

            crud.add_scheduled_post(
                req.post_type,
                req.selected_caption,
                req.scheduled_time,
                final_folder_id,
                final_event_id,
                final_uploaded_media  # Store canonical uploaded file ids and filenames
            )
            db_save_success = True
            logger.info("✅ Database save successful")
        except Exception as db_e:
            db_error_message = str(db_e)
            logger.error(f"❌ Database save error: {db_error_message}")
            raise Exception(f"Failed to save to database: {db_error_message}")

        # 4. Do not send webhook immediately; it will be triggered by the background job when scheduled_time arrives
        logger.info(f"🎯 Post scheduled successfully. Webhook will be sent at {req.scheduled_time}.")

        return schemas.ScheduleResponse(
            message="Post scheduled successfully. Webhook will be triggered at the scheduled time.",
            folder_id=folder_id,
            event_id=event_id,
            webhook_sent=False,  # Not sent yet
            webhook_status="Pending - will be sent at scheduled time"
        )
    except Exception as e:
        logger.error(f"💥 Critical error during scheduling: {e}")
        logger.exception("Full traceback:")
        # In production, you'd have more specific error handling
        raise HTTPException(status_code=500, detail=f"Scheduling failed: {str(e)}")
