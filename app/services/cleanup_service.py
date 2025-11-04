# app/services/cleanup_service.py
import datetime
from app.database import crud
from app.services import google_drive
from app.services import facebook_graph
from app.constants import DELETE_DELAY_HOURS
import logging
import requests
import os
from app.config import settings

# NOTE: publishing now goes through Facebook Graph API (Instagram endpoints)

logger = logging.getLogger(__name__)

def check_and_delete_posts():
    """Scheduled job to delete old GDrive folders."""
    logger.info("🧹 Starting background cleanup task")
    logger.info(f"   → Looking for posts older than {DELETE_DELAY_HOURS} hours")

    try:
        posts_to_delete = crud.find_posts_for_deletion(DELETE_DELAY_HOURS)

        if not posts_to_delete:
            logger.info("   → No posts found for deletion")
            return

        logger.info(f"   → Found {len(posts_to_delete)} posts for deletion")
        deleted_count = 0
        error_count = 0

        for post in posts_to_delete:
            post_id = post['id']
            folder_id = post['google_drive_folder_id']

            logger.info(f"   → Processing post {post_id} (Folder: {folder_id})")
            try:
                google_drive.delete_drive_folder(folder_id)
                crud.update_post_status(post_id, 'deleted')
                logger.info(f"   ✅ Successfully deleted post {post_id}")
                deleted_count += 1
            except Exception as e:
                logger.error(f"   ❌ Error deleting post {post_id}: {e}")
                error_count += 1
                # Optionally, update status to 'delete_failed'
                # crud.update_post_status(post_id, 'delete_failed')

        logger.info(f"🧹 Cleanup complete: {deleted_count} deleted, {error_count} errors")

    except Exception as e:
        logger.error(f"❌ Critical error in cleanup service: {e}")

def check_and_trigger_posts():
    """
    Checks for posts whose scheduled_time has arrived and triggers publishing via
    the Facebook Graph API (Instagram endpoints) using app.services.facebook_graph.
    """
    logger.info("Checking for posts to trigger...")

    posts_to_trigger = crud.find_posts_to_trigger()
    logger.info(f"Found {len(posts_to_trigger)} posts to trigger")

    for post in posts_to_trigger:
        try:
            # Get post type to determine webhook URL
            post_type = post.get('post_type', 'static')

            # (post_type will determine publish method below)

            # Prepare Instagram-ready URLs
            media_paths = post['media_paths']
            if isinstance(media_paths, str):
                import json
                media_paths = json.loads(media_paths)

            insta_urls = []
            temp_r2_files = []

            for idx, m in enumerate(media_paths):
                r2_url = m.get('r2_url')
                if r2_url and isinstance(r2_url, str) and r2_url.startswith('http'):
                    # Use existing R2 URL
                    insta_urls.append(r2_url)
                    logger.info(f"Using existing R2 URL: {r2_url}")
                else:
                    # Need to download from Drive and upload to R2
                    drive_id = m.get('uploaded_file_id')
                    if not drive_id:
                        logger.error(f"No drive_id for media {idx}")
                        continue

                    try:
                        logger.info(f"Downloading from Drive for media {idx}: {drive_id}")
                        info = google_drive.download_file_bytes(drive_id)

                        # Validate and prepare image (or handle video)
                        if post['post_type'] == 'video':
                            # For video, upload directly to R2 without temp file
                            if settings.CLOUDFLARE_R2_BUCKET and settings.CLOUDFLARE_R2_ENDPOINT:
                                import uuid
                                from io import BytesIO
                                tmp_filename = f"{uuid.uuid4()}.mp4"
                                fileobj = BytesIO(info['bytes'])
                                from app.services import r2_service
                                r2_info = r2_service.upload_fileobj_to_r2(fileobj, tmp_filename, key_prefix='videos', public=True)
                                final_url = r2_info.get('url')
                                insta_urls.append(final_url)
                                logger.info(f"Video uploaded to R2: {final_url}")
                            else:
                                # Fallback to Drive if R2 not configured
                                creds = google_drive.get_google_creds()
                                from app.services import google_drive as gd
                                service = gd.build("drive", "v3", credentials=creds)
                                media_metadata = {"name": m.get('file_name', 'video.mp4')}
                                media = gd.MediaIoBaseUpload(BytesIO(info['bytes']), mimetype='video/mp4', resumable=True)
                                uploaded_file = service.files().create(body=media_metadata, media_body=media, fields="id").execute()
                                file_id = uploaded_file.get("id")
                                public_url = google_drive.get_public_download_url(file_id)
                                insta_urls.append(public_url)
                                logger.info(f"Video uploaded to Drive: {public_url}")
                        else:
                            # For images, validate and prepare
                            final_url = validate_and_prepare_image(m.get('file_name', 'image'), info.get('bytes'))
                            insta_urls.append(final_url)
                            logger.info(f"Prepared image URL: {final_url}")
                    except Exception as e:
                        logger.error(f"Error preparing media {idx}: {e}")
                        continue

            if not insta_urls:
                logger.error(f"No valid URLs prepared for post {post['id']}")
                continue

            # Choose publish method based on post_type and call facebook_graph
            pt = post.get('post_type', 'static')
            caption = post.get('selected_caption', '')
            published = False
            status_msg = None

            if pt == 'static':
                published, status_msg = facebook_graph.publish_photo(insta_urls[0], caption)
            elif pt.startswith('carousel') or pt == 'carousel':
                published, status_msg = facebook_graph.publish_carousel(insta_urls, caption)
            elif pt == 'video':
                published, status_msg = facebook_graph.publish_video(insta_urls[0], caption)
            else:
                logger.error(f"Unsupported post_type: {pt}")
                continue

            if published:
                logger.info(f"Published post {post['id']} via Graph API: {status_msg}")
                crud.update_post_status(post['id'], 'triggered')
            else:
                logger.error(f"Publish failed for post {post['id']}: {status_msg}")

            # Clean up temp files
            for p in temp_r2_files:
                try:
                    os.remove(p)
                    logger.info(f"Cleaned up temp file: {p}")
                except Exception as e:
                    logger.error(f"Failed to clean up {p}: {e}")

        except Exception as e:
            logger.error(f"Error triggering post {post['id']}: {e}")

    logger.info("Trigger check completed")

def validate_and_prepare_image(source_url: str, source_bytes: bytes) -> str:
    """Return a public R2 URL for a JPEG that meets Instagram constraints."""
    from io import BytesIO
    from PIL import Image
    import os
    import uuid

    try:
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

        # Crop if aspect ratio out of bounds
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

        # Save to temp JPEG
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

        # Upload to R2
        if settings.CLOUDFLARE_R2_BUCKET and settings.CLOUDFLARE_R2_ENDPOINT:
            from app.services import r2_service
            r2_info = r2_service.upload_file_to_r2(tmp_path, key_prefix='instagram_ready', public=True)
            final_url = r2_info.get('url')
            os.remove(tmp_path)
            return final_url
        else:
            # Fallback to Drive
            creds = google_drive.get_google_creds()
            from app.services import google_drive as gd
            service = gd.build("drive", "v3", credentials=creds)
            media_metadata = {"name": tmp_filename}
            media = gd.MediaIoBaseUpload(open(tmp_path, 'rb'), mimetype='image/jpeg', resumable=True)
            uploaded_file = service.files().create(body=media_metadata, media_body=media, fields="id").execute()
            file_id = uploaded_file.get("id")
            public_url = google_drive.get_public_download_url(file_id)
            os.remove(tmp_path)
            return public_url

    except Exception as e:
        logger.error(f"Error in validate_and_prepare_image: {e}")
        raise
