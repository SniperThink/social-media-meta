"""
app/services/publisher_service.py

Utility that provides a simple abstraction to obtain media bytes for publishing.
Priority order:
 1. R2 URL (preferred)
 2. Google Drive file id
 3. Direct HTTP(S) URL

Returns a dict: {bytes, file_name, mime_type, source}
"""
from typing import Optional
import requests
from app.services import r2_service
from app.services import google_drive
from urllib.parse import urlparse


def get_media_bytes(media_entry: dict) -> dict:
    """Given a media entry dict (as stored in DB or returned by generator), return bytes and metadata.

    media_entry may have keys like:
      - r2_url
      - uploaded_file_id (Google Drive file id)
      - requested_path (original request path or URL)

    The function prefers R2 when available.
    """
    # 1. Prefer R2
    r2_url = media_entry.get('r2_url') or media_entry.get('url')
    if r2_url and isinstance(r2_url, str) and r2_url.startswith(('http://', 'https://')):
        try:
            data = r2_service.download_bytes_from_r2_url(r2_url)
            # Try to infer filename from URL
            parsed = urlparse(r2_url)
            fname = parsed.path.split('/')[-1]
            return {"bytes": data, "file_name": fname, "mime_type": None, "source": "r2"}
        except Exception:
            pass

    # 2. If Drive file id present, download from Drive
    drive_id = media_entry.get('uploaded_file_id')
    if drive_id:
        try:
            info = google_drive.download_file_bytes(drive_id)
            return {"bytes": info['bytes'], "file_name": info['file_name'], "mime_type": info['mime_type'], "source": "drive"}
        except Exception:
            pass

    # 3. If requested_path is a URL, fetch it over HTTP
    req = media_entry.get('requested_path') or media_entry.get('url')
    if req and isinstance(req, str) and req.startswith(('http://', 'https://')):
        try:
            resp = requests.get(req, timeout=20)
            resp.raise_for_status()
            # Try to infer filename from URL or Content-Disposition
            parsed = urlparse(req)
            fname = parsed.path.split('/')[-1] or 'file'
            mime = resp.headers.get('Content-Type')
            return {"bytes": resp.content, "file_name": fname, "mime_type": mime, "source": "http"}
        except Exception:
            pass

    # 4. If requested_path is a local file path, read it
    if req and isinstance(req, str) and not req.startswith(('http://', 'https://')):
        try:
            with open(req, 'rb') as f:
                data = f.read()
            fname = req.split('/')[-1] or req.split('\\')[-1]
            return {"bytes": data, "file_name": fname, "mime_type": None, "source": "local"}
        except Exception:
            pass

    raise RuntimeError("No available source found for media entry")
