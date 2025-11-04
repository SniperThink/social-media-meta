from fastapi import APIRouter, HTTPException
from app.models import schemas
from app.services import publisher_service, google_drive
from app.services import google_calender
from app.database import crud
from app.utils.retry import retry
import tempfile
import os
import uuid
import requests
from typing import Dict
from io import BytesIO
from PIL import Image
from app.services import r2_service
from app.config import settings
from app.services import facebook_graph

router = APIRouter(prefix="/api/webhook", tags=["webhook"])

# Publishing is performed via the Facebook Graph API (Instagram endpoints)
# using the helpers in `app.services.facebook_graph`.




@router.post("/schedule", response_model=schemas.WebhookResponse)
def webhook_schedule(req: schemas.WebhookRequest):
    """Webhook endpoint that accepts a scheduling request and ensures media is available.

    Behavior:
      - For each media entry, prefer R2 via publisher_service.get_media_bytes
      - If media is not already uploaded to Drive (no uploaded_file_id), upload it to Drive
      - Create Google Calendar event and DB scheduled_post using existing flows
      - Retries transient failures using the simple retry helper
    """
    # 1) Ensure each media is downloadable (R2-first) and gather temp file paths for Drive upload
    temp_paths = []
    updated_media_entries = []

    for entry in req.media:
        entry_dict = entry.dict()
        try:
            # Attempt to fetch bytes via publisher helpers (R2 > Drive > HTTP)
            b = retry(publisher_service.get_media_bytes, retries=2, delay=1.0, backoff=2.0, args=(entry_dict,))
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Failed to fetch media: {entry.requested_path or entry.r2_url} - {e}")

        # If drive id present, keep it; else write bytes to temp file to upload
        if entry.uploaded_file_id:
            updated_media_entries.append(entry_dict)
        else:
            tmp_dir = os.path.join('app', 'frontend', 'temp_generated_images')
            os.makedirs(tmp_dir, exist_ok=True)
            filename = entry.file_name or f"{uuid.uuid4()}"
            tmp_path = os.path.join(tmp_dir, filename)
            with open(tmp_path, 'wb') as fh:
                fh.write(b['bytes'])
            temp_paths.append(tmp_path)
            # Update requested_path to point to the temp file so the Drive uploader will pick it
            entry_dict['requested_path'] = tmp_path
            updated_media_entries.append(entry_dict)

    # 2) Upload to Drive (this function will create a folder and upload files)
    try:
        folder_id, uploaded_media = retry(
            google_drive.upload_files_to_drive,
            retries=2,
            delay=1.0,
            backoff=2.0,
            args=( [m['requested_path'] for m in updated_media_entries], req.selected_caption, req.post_type )
        )
    except Exception as e:
        # Clean up temp files
        for p in temp_paths:
            try:
                os.remove(p)
            except Exception:
                pass
        raise HTTPException(status_code=502, detail=f"Drive upload failed: {e}")

    # 3) Create calendar event
    try:
        event_id = retry(google_calender.create_calendar_event, retries=2, delay=1.0, backoff=2.0, args=(req.scheduled_time, req.selected_caption, folder_id, req.post_type, req.timezone))
    except Exception as e:
        # Attempt to delete created folder to avoid orphaned folders
        try:
            google_drive.delete_drive_folder(folder_id)
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Calendar event creation failed: {e}")

    # NOTE: move DB persistence after we enrich uploaded_media with r2_url so DB stores canonical R2 URLs when available

    # Publishing will be done via the Facebook Graph API (Instagram) using
    # `app.services.facebook_graph`. We build `public_urls` below and then
    # call the appropriate publish helper (photo/carousel/video).

    # Prepare Instagram-ready public URLs for the Make webhook.
    # For images: Prefer R2, then make Drive files public if R2 not available.
    # For videos: Use R2 URL directly without validation.
    public_urls = []
    temp_r2_files = []

    def validate_and_prepare_image(source_url: str, source_bytes: bytes) -> str:
        """Return a public URL for a JPEG that meets Instagram constraints.

        If R2 is configured, upload processed JPEG to R2 and return the URL.
        Otherwise, make the Drive file public.
        """
        # Open with PIL
        img = Image.open(BytesIO(source_bytes)).convert('RGB')
        width, height = img.size
        ratio = width / height if height else 0

        # Aspect ratio must be between 0.8 (4:5) and 1.91
        MIN_RATIO = 4/5
        MAX_RATIO = 1.91
        # Width constraints
        MIN_WIDTH = 320
        MAX_WIDTH = 1440

        # Resize if width out of bounds
        if width < MIN_WIDTH:
            new_w = MIN_WIDTH
            new_h = int(new_w / ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            width, height = img.size
            ratio = width / height
        elif width > MAX_WIDTH:
            new_w = MAX_WIDTH
            new_h = int(new_w / ratio)
            img = img.resize((new_w, new_h), Image.LANCZOS)
            width, height = img.size
            ratio = width / height

        # If aspect ratio is out of bounds, attempt to crop center to nearest allowed ratio
        if ratio < MIN_RATIO or ratio > MAX_RATIO:
            # Compute target ratio clamp
            target_ratio = max(MIN_RATIO, min(MAX_RATIO, ratio))
            target_w = width
            target_h = int(round(target_w / target_ratio))
            if target_h <= height:
                # crop vertically center
                top = (height - target_h)//2
                img = img.crop((0, top, target_w, top + target_h))
            else:
                # crop horizontally
                target_h = height
                target_w = int(round(target_h * target_ratio))
                left = (width - target_w)//2
                img = img.crop((left, 0, left + target_w, target_h))

        # Save to temp JPEG and ensure size <= 8MiB by adjusting quality
        quality = 95
        temp_dir = os.path.join('app', 'frontend', 'temp_generated_images')
        os.makedirs(temp_dir, exist_ok=True)
        tmp_filename = f"{uuid.uuid4()}.jpg"
        tmp_path = os.path.join(temp_dir, tmp_filename)

        while True:
            with open(tmp_path, 'wb') as out_f:
                img.save(out_f, format='JPEG', quality=quality)
            size = os.path.getsize(tmp_path)
            if size <= 8 * 1024 * 1024 or quality <= 40:
                break
            quality = int(quality * 0.85)

        # Upload to R2 if configured
        if settings.CLOUDFLARE_R2_BUCKET and settings.CLOUDFLARE_R2_ENDPOINT:
            try:
                r2_info = r2_service.upload_file_to_r2(tmp_path, key_prefix='instagram_ready', public=True)
                temp_r2_files.append(tmp_path)
                return r2_info.get('url')
            except Exception:
                pass

        # Fallback: upload to Drive and make public
        try:
            creds = google_drive.get_google_creds()
            service = google_drive.build("drive", "v3", credentials=creds)
            with open(tmp_path, 'rb') as f:
                media_metadata = {"name": tmp_filename}
                media = google_drive.MediaIoBaseUpload(f, mimetype='image/jpeg', resumable=True)
                uploaded_file = service.files().create(body=media_metadata, media_body=media, fields="id").execute()
                file_id = uploaded_file.get("id")
            public_url = google_drive.get_public_download_url(file_id)
            temp_r2_files.append(tmp_path)
            return public_url
        except Exception as e:
            print(f"Failed to upload to Drive: {e}")
            raise RuntimeError('Unable to create public URL for Instagram')

    if req.post_type.lower() == 'video':
        # For videos, just use the R2 URL directly
        for idx, m in enumerate(uploaded_media):
            r2_url = m.get('r2_url') or m.get('url')
            if r2_url and isinstance(r2_url, str) and r2_url.startswith('http'):
                public_urls.append(r2_url)
                uploaded_media[idx]['r2_url'] = r2_url
    else:
        # For images, validate and prepare
        # Iterate uploaded_media and ensure public JPEG URLs for Instagram
        for idx, m in enumerate(uploaded_media):
            # Prefer existing r2_url
            r2_url = m.get('r2_url') or m.get('url')
            if r2_url and isinstance(r2_url, str) and r2_url.startswith('http'):
                # Download bytes for validation
                try:
                    # Prefer r2 service for downloading if possible
                    try:
                        img_bytes = r2_service.download_bytes_from_r2_url(r2_url)
                    except Exception:
                        resp = requests.get(r2_url, timeout=10)
                        resp.raise_for_status()
                        img_bytes = resp.content
                    # Validate and possibly convert/upload again to R2 or Drive
                    final_url = validate_and_prepare_image(r2_url, img_bytes)
                    public_urls.append(final_url)
                    # persist r2_url into uploaded_media entry
                    uploaded_media[idx]['r2_url'] = final_url
                except Exception:
                    # If validation fails, try Drive fallback below
                    pass

        # If no public_urls yet, try using Drive files
        if not public_urls:
            for idx, m in enumerate(uploaded_media):
                drive_id = m.get('uploaded_file_id')
                if not drive_id:
                    continue
                try:
                    info = google_drive.download_file_bytes(drive_id)
                    final_url = validate_and_prepare_image(info.get('file_name'), info.get('bytes'))
                    public_urls.append(final_url)
                    uploaded_media[idx]['r2_url'] = final_url
                except Exception:
                    continue

        # If still no valid public URL, fail
        if not public_urls:
            webhook_sent = False
            webhook_status = 'No valid public JPEG URL available for Instagram'
            # Clean up temp files
            for p in temp_paths + temp_r2_files:
                try:
                    os.remove(p)
                except Exception:
                    pass
            return schemas.WebhookResponse(message="Webhook scheduled but Instagram payload failed", folder_id=folder_id, event_id=event_id, webhook_sent=webhook_sent, webhook_status=webhook_status)

    # Decide how we'll publish via Graph API
    publish_type = 'photo'
    publish_source = None
    pt = req.post_type.lower() if isinstance(req.post_type, str) else ''
    if pt == 'static':
        publish_type = 'photo'
        publish_source = public_urls[0] if public_urls else None
    elif pt.startswith('carousel') or pt == 'carousel':
        publish_type = 'carousel'
        publish_source = public_urls
    elif pt == 'video':
        publish_type = 'video'
        publish_source = public_urls[0] if public_urls else None

    # Persist enriched media metadata into DB now
    try:
        crud.add_scheduled_post(req.post_type, req.selected_caption, req.scheduled_time, folder_id, event_id, media_paths=uploaded_media)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB insert failed: {e}")

    # Publish using Facebook Graph API (Instagram endpoints) if configured
    webhook_sent = False
    webhook_status = None
    try:
        if not settings.FACEBOOK_PAGE_ACCESS_TOKEN or not settings.INSTAGRAM_USER_ID:
            raise RuntimeError("Facebook Graph API credentials not configured (FACEBOOK_PAGE_ACCESS_TOKEN / INSTAGRAM_USER_ID)")

        if publish_type == 'video':
            success, status = facebook_graph.publish_video(publish_source, req.selected_caption)
        elif publish_type == 'carousel':
            success, status = facebook_graph.publish_carousel(publish_source or [], req.selected_caption)
        else:
            success, status = facebook_graph.publish_photo(publish_source, req.selected_caption)

        webhook_sent = bool(success)
        webhook_status = status
    except Exception as e:
        webhook_sent = False
        webhook_status = str(e)

    # 5) Clean up temp files
    for p in temp_paths:
        try:
            os.remove(p)
        except Exception:
            pass

    return schemas.WebhookResponse(message="Webhook scheduled successfully", folder_id=folder_id, event_id=event_id, webhook_sent=webhook_sent, webhook_status=webhook_status)


def create_carousel_webhook_endpoint(num_images: int):
    """Factory function to create carousel webhook endpoints."""
    @router.post(f"/carousel_{num_images}", response_model=schemas.WebhookResponse)
    def carousel_webhook(req: schemas.WebhookRequest):
        """Webhook endpoint for carousel posts with specific number of images."""
        # Validate exact number of media entries
        if len(req.media) != num_images:
            raise HTTPException(status_code=400, detail=f"Carousel {num_images} requires exactly {num_images} media entries, got {len(req.media)}")

        # Set post_type to carousel_N
        req.post_type = f'carousel_{num_images}'

        # Reuse the main webhook logic but with specific webhook URL
        # For simplicity, we'll duplicate the logic here with the specific URL
        # 1) Ensure each media is downloadable (R2-first) and gather temp file paths for Drive upload
        temp_paths = []
        updated_media_entries = []

        for entry in req.media:
            entry_dict = entry.dict()
            try:
                # Attempt to fetch bytes via publisher helpers (R2 > Drive > HTTP)
                b = retry(publisher_service.get_media_bytes, retries=2, delay=1.0, backoff=2.0, args=(entry_dict,))
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"Failed to fetch media: {entry.requested_path or entry.r2_url} - {e}")

            # If drive id present, keep it; else write bytes to temp file to upload
            if entry.uploaded_file_id:
                updated_media_entries.append(entry_dict)
            else:
                tmp_dir = os.path.join('app', 'frontend', 'temp_generated_images')
                os.makedirs(tmp_dir, exist_ok=True)
                filename = entry.file_name or f"{uuid.uuid4()}"
                tmp_path = os.path.join(tmp_dir, filename)
                with open(tmp_path, 'wb') as fh:
                    fh.write(b['bytes'])
                temp_paths.append(tmp_path)
                # Update requested_path to point to the temp file so the Drive uploader will pick it
                entry_dict['requested_path'] = tmp_path
                updated_media_entries.append(entry_dict)

        # 2) Upload to Drive
        try:
            folder_id, uploaded_media = retry(
                google_drive.upload_files_to_drive,
                retries=2,
                delay=1.0,
                backoff=2.0,
                args=( [m['requested_path'] for m in updated_media_entries], req.selected_caption, req.post_type )
            )
        except Exception as e:
            # Clean up temp files
            for p in temp_paths:
                try:
                    os.remove(p)
                except Exception:
                    pass
            raise HTTPException(status_code=502, detail=f"Drive upload failed: {e}")

        # 3) Create calendar event
        try:
            event_id = retry(google_calender.create_calendar_event, retries=2, delay=1.0, backoff=2.0, args=(req.scheduled_time, req.selected_caption, folder_id, req.post_type, req.timezone))
        except Exception as e:
            # Attempt to delete created folder to avoid orphaned folders
            try:
                google_drive.delete_drive_folder(folder_id)
            except Exception:
                pass
            raise HTTPException(status_code=502, detail=f"Calendar event creation failed: {e}")

        # 4) Prepare Instagram-ready public URLs
        public_urls = []
        temp_r2_files = []

        def validate_and_prepare_image(source_url: str, source_bytes: bytes) -> str:
            """Return a public URL for a JPEG that meets Instagram constraints."""
            # Open with PIL
            img = Image.open(BytesIO(source_bytes)).convert('RGB')
            width, height = img.size
            ratio = width / height if height else 0

            # Aspect ratio must be between 0.8 (4:5) and 1.91
            MIN_RATIO = 4/5
            MAX_RATIO = 1.91
            MIN_WIDTH = 320
            MAX_WIDTH = 1440

            # Resize if width out of bounds
            if width < MIN_WIDTH:
                new_w = MIN_WIDTH
                new_h = int(new_w / ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                width, height = img.size
                ratio = width / height
            elif width > MAX_WIDTH:
                new_w = MAX_WIDTH
                new_h = int(new_w / ratio)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                width, height = img.size
                ratio = width / height

            # If aspect ratio is out of bounds, attempt to crop center to nearest allowed ratio
            if ratio < MIN_RATIO or ratio > MAX_RATIO:
                target_ratio = max(MIN_RATIO, min(MAX_RATIO, ratio))
                target_w = width
                target_h = int(round(target_w / target_ratio))
                if target_h <= height:
                    top = (height - target_h)//2
                    img = img.crop((0, top, target_w, top + target_h))
                else:
                    target_h = height
                    target_w = int(round(target_h * target_ratio))
                    left = (width - target_w)//2
                    img = img.crop((left, 0, left + target_w, target_h))

            # Save to temp JPEG and ensure size <= 8MiB by adjusting quality
            quality = 95
            temp_dir = os.path.join('app', 'frontend', 'temp_generated_images')
            os.makedirs(temp_dir, exist_ok=True)
            tmp_filename = f"{uuid.uuid4()}.jpg"
            tmp_path = os.path.join(temp_dir, tmp_filename)

            while True:
                with open(tmp_path, 'wb') as out_f:
                    img.save(out_f, format='JPEG', quality=quality)
                size = os.path.getsize(tmp_path)
                if size <= 8 * 1024 * 1024 or quality <= 40:
                    break
                quality = int(quality * 0.85)

            # Upload to R2 if configured
            if settings.CLOUDFLARE_R2_BUCKET and settings.CLOUDFLARE_R2_ENDPOINT:
                try:
                    r2_info = r2_service.upload_file_to_r2(tmp_path, key_prefix='instagram_ready', public=True)
                    temp_r2_files.append(tmp_path)
                    return r2_info.get('url')
                except Exception:
                    pass

            # Fallback: upload to Drive and make public
            try:
                creds = google_drive.get_google_creds()
                service = google_drive.build("drive", "v3", credentials=creds)
                with open(tmp_path, 'rb') as f:
                    media_metadata = {"name": tmp_filename}
                    media = google_drive.MediaIoBaseUpload(f, mimetype='image/jpeg', resumable=True)
                    uploaded_file = service.files().create(body=media_metadata, media_body=media, fields="id").execute()
                    file_id = uploaded_file.get("id")
                public_url = google_drive.get_public_download_url(file_id)
                temp_r2_files.append(tmp_path)
                return public_url
            except Exception as e:
                print(f"Failed to upload to Drive: {e}")
                raise RuntimeError('Unable to create public URL for Instagram')

        # Prepare URLs for images
        for idx, m in enumerate(uploaded_media):
            r2_url = m.get('r2_url') or m.get('url')
            if r2_url and isinstance(r2_url, str) and r2_url.startswith('http'):
                try:
                    try:
                        img_bytes = r2_service.download_bytes_from_r2_url(r2_url)
                    except Exception:
                        resp = requests.get(r2_url, timeout=10)
                        resp.raise_for_status()
                        img_bytes = resp.content
                    final_url = validate_and_prepare_image(r2_url, img_bytes)
                    public_urls.append(final_url)
                    uploaded_media[idx]['r2_url'] = final_url
                except Exception:
                    pass

        # If no public_urls yet, try using Drive files
        if not public_urls:
            for idx, m in enumerate(uploaded_media):
                drive_id = m.get('uploaded_file_id')
                if not drive_id:
                    continue
                try:
                    info = google_drive.download_file_bytes(drive_id)
                    final_url = validate_and_prepare_image(info.get('file_name'), info.get('bytes'))
                    public_urls.append(final_url)
                    uploaded_media[idx]['r2_url'] = final_url
                except Exception:
                    continue

        # If still no valid public URL, fail
        if not public_urls:
            webhook_sent = False
            webhook_status = 'No valid public JPEG URL available for Instagram'
            # Clean up temp files
            for p in temp_paths + temp_r2_files:
                try:
                    os.remove(p)
                except Exception:
                    pass
            return schemas.WebhookResponse(message="Webhook scheduled but Instagram payload failed", folder_id=folder_id, event_id=event_id, webhook_sent=webhook_sent, webhook_status=webhook_status)


        # Persist enriched media metadata into DB
        try:
            crud.add_scheduled_post(req.post_type, req.selected_caption, req.scheduled_time, folder_id, event_id, media_paths=uploaded_media)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DB insert failed: {e}")

        # Publish carousel via Graph API
        webhook_sent = False
        webhook_status = None
        try:
            if not settings.FACEBOOK_PAGE_ACCESS_TOKEN or not settings.INSTAGRAM_USER_ID:
                raise RuntimeError("Facebook Graph API credentials not configured (FACEBOOK_PAGE_ACCESS_TOKEN / INSTAGRAM_USER_ID)")
            success, status = facebook_graph.publish_carousel(public_urls, req.selected_caption)
            webhook_sent = bool(success)
            webhook_status = status
        except Exception as e:
            webhook_sent = False
            webhook_status = str(e)

        # 6) Clean up temp files
        for p in temp_paths:
            try:
                os.remove(p)
            except Exception:
                pass

        return schemas.WebhookResponse(message=f"Carousel {num_images} webhook scheduled successfully", folder_id=folder_id, event_id=event_id, webhook_sent=webhook_sent, webhook_status=webhook_status)

    return carousel_webhook


# Create the carousel endpoints
for num in range(2, 11):
    create_carousel_webhook_endpoint(num)
