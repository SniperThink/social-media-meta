# app/services/google_drive.py
import datetime
import io
import os
import requests
import uuid
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseUpload
from app.utils.auth import get_google_creds
from googleapiclient.http import MediaIoBaseDownload
from app.services import r2_service
import io

def create_social_media_root_folder(service):
    """
    Creates or finds the root 'Social Media Automation' folder.
    """
    # Check if folder already exists
    query = "name='Social Media Automation' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    results = service.files().list(q=query, fields="files(id, name)").execute()
    items = results.get('files', [])

    if items:
        print(f"Found existing root folder: {items[0]['name']} (ID: {items[0]['id']})")
        return items[0]['id']
    else:
        # Create new root folder
        file_metadata = {
            "name": "Social Media Automation",
            "mimeType": "application/vnd.google-apps.folder",
        }
        folder = service.files().create(body=file_metadata, fields="id").execute()
        folder_id = folder.get("id")
        print(f"Created root GDrive folder: Social Media Automation (ID: {folder_id})")
        return folder_id

def upload_files_to_drive(selected_media_paths: list, selected_caption: str, post_type: str = None):
    """
    Creates a new folder under 'Social Media Automation' and uploads actual media files.
    """
    creds = get_google_creds()
    try:
        service = build("drive", "v3", credentials=creds)

        # 1. Ensure root folder exists
        root_folder_id = create_social_media_root_folder(service)

        # 2. Create post-specific subfolder with post type prefix
        timestamp = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        post_folder_name = f"{post_type}_{timestamp}" if post_type else timestamp
        file_metadata = {
            "name": post_folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [root_folder_id]
        }
        post_folder = service.files().create(body=file_metadata, fields="id").execute()
        post_folder_id = post_folder.get("id")
        print(f"Created post GDrive folder: {post_folder_name} (ID: {post_folder_id})")

        # 3. Upload actual media files
        uploaded_media = []
        missing_media = []

        for i, media_path in enumerate(selected_media_paths):
            try:
                # Handle URLs: download to memory, upload to R2, then to Drive from R2 URL
                if isinstance(media_path, str) and media_path.startswith(('http://', 'https://')):
                    try:
                        resp = requests.get(media_path, timeout=20)
                        resp.raise_for_status()
                        content = resp.content

                        # Extract file extension from URL or Content-Type
                        url_path = media_path.split('?')[0]  # Remove query params
                        url_filename = os.path.basename(url_path)
                        if '.' in url_filename:
                            ext = os.path.splitext(url_filename)[1]
                        else:
                            content_type = resp.headers.get('content-type', '').lower()
                            if 'png' in content_type:
                                ext = '.png'
                            elif 'jpeg' in content_type or 'jpg' in content_type:
                                ext = '.jpg'
                            elif 'gif' in content_type:
                                ext = '.gif'
                            elif 'mp4' in content_type:
                                ext = '.mp4'
                            else:
                                ext = '.bin'

                        # Upload to R2 first
                        r2_url = None
                        if hasattr(r2_service, 'upload_file_to_r2') and r2_service.settings.CLOUDFLARE_R2_BUCKET:
                            try:
                                # Create a temporary key for R2 upload
                                temp_key = f"temp_{uuid.uuid4()}{ext}"
                                # Use R2Client directly to upload from bytes
                                r2_client = r2_service.R2Client()
                                r2_client.s3.put_object(
                                    Bucket=r2_client.bucket,
                                    Key=temp_key,
                                    Body=content,
                                    ACL='public-read'
                                )
                                if r2_service.settings.CLOUDFLARE_R2_PUBLIC_URL:
                                    r2_url = f"{r2_service.settings.CLOUDFLARE_R2_PUBLIC_URL}/{temp_key}"
                                else:
                                    r2_url = f"https://{r2_client.bucket}.r2.cloudflarestorage.com/{temp_key}"
                                print(f"Uploaded to R2: {r2_url}")
                            except Exception as e:
                                print(f"R2 upload failed: {e}")

                        # Now upload to Drive from R2 URL
                        if r2_url:
                            # Download from R2 URL to get bytes for Drive upload
                            drive_resp = requests.get(r2_url, timeout=20)
                            drive_resp.raise_for_status()
                            drive_content = drive_resp.content
                        else:
                            # Fallback to original content if R2 failed
                            drive_content = content

                        file_name = f"media_{uuid.uuid4()}{ext}"
                        mime_type = 'image/png' if ext.lower() in ('.png', '.jpg', '.jpeg') else 'video/mp4'

                        media_metadata = {"name": file_name, "parents": [post_folder_id]}
                        media = MediaIoBaseUpload(io.BytesIO(drive_content), mimetype=mime_type, resumable=True)
                        uploaded_file = service.files().create(body=media_metadata, media_body=media, fields="id").execute()
                        file_id = uploaded_file.get("id")

                        uploaded_media.append({
                            "requested_path": media_path,
                            "uploaded_file_id": file_id,
                            "file_name": file_name,
                            "mime_type": mime_type,
                            "r2_url": r2_url
                        })
                        print(f"Uploaded media: {file_name} (ID: {file_id})")

                    except Exception as e:
                        print(f"Warning: Failed to process media URL {media_path}: {e}")
                        missing_media.append(media_path)
                        continue

                # Handle local files: upload to R2 first, then to Drive from R2 URL
                else:
                    # Convert relative path to absolute path for known temp dirs
                    if isinstance(media_path, str) and media_path.startswith('/temp_generated_images/'):
                        abs_media_path = os.path.join('app/frontend', media_path.lstrip('/'))
                    elif isinstance(media_path, str) and media_path.startswith('/temp_generated_videos/'):
                        abs_media_path = os.path.join('app/frontend', media_path.lstrip('/'))
                    else:
                        abs_media_path = media_path

                    if not os.path.exists(abs_media_path):
                        missing_media.append(abs_media_path)
                        print(f"Warning: Media file not found: {abs_media_path}")
                        continue

                    file_name = os.path.basename(abs_media_path)
                    mime_type = 'image/png' if file_name.lower().endswith(('.png', '.jpg', '.jpeg')) else 'video/mp4'

                    # Upload to R2 first
                    r2_url = None
                    if hasattr(r2_service, 'upload_file_to_r2') and r2_service.settings.CLOUDFLARE_R2_BUCKET:
                        try:
                            r2_info = r2_service.upload_file_to_r2(abs_media_path, key_prefix='drive_backup', public=True)
                            r2_url = r2_info.get('url')
                            print(f"Uploaded to R2: {r2_url}")
                        except Exception as e:
                            print(f"R2 upload failed: {e}")

                    # Upload to Drive from R2 URL if available, otherwise from local file
                    if r2_url:
                        try:
                            drive_resp = requests.get(r2_url, timeout=20)
                            drive_resp.raise_for_status()
                            drive_content = drive_resp.content
                            media = MediaIoBaseUpload(io.BytesIO(drive_content), mimetype=mime_type, resumable=True)
                        except Exception as e:
                            print(f"Failed to download from R2 for Drive upload, falling back to local file: {e}")
                            with open(abs_media_path, 'rb') as f:
                                media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True)
                    else:
                        with open(abs_media_path, 'rb') as f:
                            media = MediaIoBaseUpload(f, mimetype=mime_type, resumable=True)

                    media_metadata = {"name": file_name, "parents": [post_folder_id]}
                    uploaded_file = service.files().create(body=media_metadata, media_body=media, fields="id").execute()
                    file_id = uploaded_file.get("id")

                    uploaded_media.append({
                        "requested_path": media_path,
                        "uploaded_file_id": file_id,
                        "file_name": file_name,
                        "mime_type": mime_type,
                        "r2_url": r2_url
                    })
                    print(f"Uploaded media: {file_name} (ID: {file_id})")

            except Exception as e:
                print(f"Warning: Failed to process media {media_path}: {e}")
                missing_media.append(media_path)
                continue

        # If any requested media were missing, clean up created folder and abort
        if missing_media:
            print(f"Error: Missing {len(missing_media)} media files. Aborting upload and cleaning up created Drive folder.")
            try:
                service.files().delete(fileId=post_folder_id).execute()
                print(f"Deleted created post folder {post_folder_id} due to upload errors.")
            except Exception as e:
                print(f"Warning: Failed to delete created Drive folder {post_folder_id}: {e}")
            raise Exception(f"Missing media files: {missing_media}")

        # 4. Upload the caption
        caption_fh = io.BytesIO(selected_caption.encode('utf-8'))
        caption_metadata = {"name": "caption.txt", "parents": [post_folder_id]}
        caption_media = MediaIoBaseUpload(caption_fh, mimetype='text/plain', resumable=True)
        caption_file = service.files().create(body=caption_metadata, media_body=caption_media, fields="id").execute()
        print(f"Uploaded caption: caption.txt (ID: {caption_file.get('id')})")

        print(f"Uploaded {len(uploaded_media)} media files and 1 caption to folder {post_folder_name}.")
        # Return folder id and uploaded media metadata so callers can store canonical file ids
        return post_folder_id, uploaded_media

    except HttpError as error:
        print(f"An error occurred during GDrive upload: {error}")
        raise
    except Exception as e:
        print(f"A general error occurred: {e}")
        raise

def delete_drive_folder(folder_id: str):
    """Permanently deletes a folder from Google Drive."""
    creds = get_google_creds()
    try:
        service = build("drive", "v3", credentials=creds)
        service.files().delete(fileId=folder_id).execute()
        print(f"Successfully deleted GDrive folder: {folder_id}")
    except HttpError as error:
        if error.resp.status == 404:
             print(f"Folder {folder_id} already deleted or not found.")
        else:
            print(f"An error occurred while deleting folder {folder_id}: {error}")
            # Don't re-raise, just log it, so cleanup can continue


def get_public_download_url(file_id: str) -> str:
    """Make a Drive file public and return the direct download URL."""
    creds = get_google_creds()
    try:
        service = build("drive", "v3", credentials=creds)
        # Make file public
        permission = {
            'type': 'anyone',
            'role': 'reader'
        }
        service.permissions().create(fileId=file_id, body=permission).execute()
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    except HttpError as error:
        print(f"Error making Drive file {file_id} public: {error}")
        raise
    except Exception as e:
        print(f"General error making Drive file {file_id} public: {e}")
        raise

def download_file_bytes(file_id: str) -> dict:
    """Download a file from Google Drive and return a dict with keys: bytes, file_name, mime_type."""
    creds = get_google_creds()
    try:
        service = build("drive", "v3", credentials=creds)
        meta = service.files().get(fileId=file_id, fields="name,mimeType").execute()
        file_name = meta.get('name')
        mime_type = meta.get('mimeType')

        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)
        return {"bytes": fh.read(), "file_name": file_name, "mime_type": mime_type}
    except HttpError as error:
        print(f"Error downloading Drive file {file_id}: {error}")
        raise
    except Exception as e:
        print(f"General error downloading Drive file {file_id}: {e}")
        raise
