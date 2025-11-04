"""
Minimal Facebook Graph API helper for publishing Instagram content.

This module provides helpers to publish single-image posts, carousels, and videos
to an Instagram Business/Creator account via the Facebook Graph API.

Note: The app must provide `FACEBOOK_PAGE_ACCESS_TOKEN` and `INSTAGRAM_USER_ID`
in its environment (`.env` -> `app.config.settings`).
"""
from typing import List, Tuple, Optional
import requests
from app.config import settings


def _graph_url(path: str) -> str:
    version = settings.FACEBOOK_GRAPH_API_VERSION or "v17.0"
    return f"https://graph.facebook.com/{version}/{path}"


def _post(path: str, data: dict, timeout: int = 30) -> dict:
    url = _graph_url(path)
    resp = requests.post(url, data=data, timeout=timeout)
    try:
        return {"status_code": resp.status_code, "json": resp.json(), "text": resp.text}
    except Exception:
        return {"status_code": resp.status_code, "json": None, "text": resp.text}


def _video_post(path: str, data: dict, timeout: int = 60) -> dict:
    """Use the graph-video.facebook.com host for video uploads/operations.

    The Graph API uses a separate domain for large media uploads.
    """
    version = settings.FACEBOOK_GRAPH_API_VERSION or "v17.0"
    url = f"https://graph-video.facebook.com/{version}/{path}"
    resp = requests.post(url, data=data, timeout=timeout)
    try:
        return {"status_code": resp.status_code, "json": resp.json(), "text": resp.text}
    except Exception:
        return {"status_code": resp.status_code, "json": None, "text": resp.text}


def publish_photo(image_url: str, caption: str) -> Tuple[bool, str]:
    """Publish a single photo to Instagram using the Graph API.

    Returns: (success, status_message)
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    ig_user = settings.INSTAGRAM_USER_ID
    if not token or not ig_user:
        return False, "Facebook/Instagram credentials not configured"

    # Step 1: create media container
    data = {
        "image_url": image_url,
        "caption": caption,
        "access_token": token,
    }
    res_create = _post(f"{ig_user}/media", data)
    if res_create.get("status_code") not in (200, 201) or not res_create.get("json"):
        return False, f"Failed to create media container: {res_create.get('text')}"

    creation_id = res_create["json"].get("id")
    if not creation_id:
        return False, f"No creation id returned: {res_create.get('text')}"

    # Step 2: publish
    res_publish = _post(f"{ig_user}/media_publish", {"creation_id": creation_id, "access_token": token})
    if res_publish.get("status_code") in (200, 201):
        return True, f"Published: {res_publish.get('text')}"
    return False, f"Publish failed: {res_publish.get('text')}"


def publish_carousel(image_urls: List[str], caption: str) -> Tuple[bool, str]:
    """Publish a carousel (album) to Instagram.

    Flow:
      - create individual children containers with is_carousel_item=true
      - create a parent container with children list
      - publish it
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    ig_user = settings.INSTAGRAM_USER_ID
    if not token or not ig_user:
        return False, "Facebook/Instagram credentials not configured"

    child_ids = []
    for url in image_urls:
        data = {"image_url": url, "is_carousel_item": True, "access_token": token}
        res = _post(f"{ig_user}/media", data)
        if res.get("status_code") not in (200, 201) or not res.get("json"):
            return False, f"Failed creating child media: {res.get('text')}"
        cid = res["json"].get("id")
        if not cid:
            return False, f"No child id returned: {res.get('text')}"
        child_ids.append(cid)

    # Create parent container with children
    children_param = ",".join(child_ids)
    data = {"children": children_param, "caption": caption, "access_token": token}
    res_parent = _post(f"{ig_user}/media", data)
    if res_parent.get("status_code") not in (200, 201) or not res_parent.get("json"):
        return False, f"Failed to create parent carousel container: {res_parent.get('text')}"

    creation_id = res_parent["json"].get("id")
    if not creation_id:
        return False, f"No creation id for carousel: {res_parent.get('text')}"

    res_publish = _post(f"{ig_user}/media_publish", {"creation_id": creation_id, "access_token": token})
    if res_publish.get("status_code") in (200, 201):
        return True, f"Carousel published: {res_publish.get('text')}"
    return False, f"Carousel publish failed: {res_publish.get('text')}"


def publish_video(video_url: str, caption: str) -> Tuple[bool, str]:
    """Publish a video post to Instagram.

    Note: video publishing may take longer; this helper performs the basic create+publish flow.
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    ig_user = settings.INSTAGRAM_USER_ID
    if not token or not ig_user:
        return False, "Facebook/Instagram credentials not configured"

    # Create video container via graph-video host
    data = {"video_url": video_url, "caption": caption, "access_token": token}
    res_create = _video_post(f"{ig_user}/media", data, timeout=120)
    if res_create.get("status_code") not in (200, 201) or not res_create.get("json"):
        return False, f"Failed to create video container: {res_create.get('text')}"

    creation_id = res_create["json"].get("id")
    if not creation_id:
        return False, f"No creation id returned for video: {res_create.get('text')}"

    res_publish = _post(f"{ig_user}/media_publish", {"creation_id": creation_id, "access_token": token}, timeout=60)
    if res_publish.get("status_code") in (200, 201):
        return True, f"Video published: {res_publish.get('text')}"
    return False, f"Video publish failed: {res_publish.get('text')}"
