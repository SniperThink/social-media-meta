"""
Minimal Facebook Graph API helper for publishing Instagram content.

This module provides helpers to publish single-image posts, carousels, and videos
to an Instagram Business/Creator account via the Facebook Graph API.

Credentials:
 - Required: `FACEBOOK_PAGE_ACCESS_TOKEN`
 - Optional: `INSTAGRAM_USER_ID` (if omitted, we resolve it once from the token)

If `INSTAGRAM_USER_ID` is not set, we call Graph API with the Page access token to
resolve the linked `instagram_business_account.id` and cache it for this process.
"""
from typing import List, Tuple, Optional
import requests
from app.config import settings

# Cache for resolved IG user id when not provided explicitly via settings
_CACHED_IG_USER_ID: Optional[str] = None


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


def _resolve_ig_user_id() -> Optional[str]:
    """Return the Instagram Business/Creator account ID for the current token.

    Order of resolution:
      1) If settings.INSTAGRAM_USER_ID is set, use it
      2) If cached value exists, use it
      3) Query Graph: GET /me?fields=instagram_business_account{id}

    Note: This assumes `FACEBOOK_PAGE_ACCESS_TOKEN` is a Page access token
    for a Page linked to the target Instagram professional account.
    """
    global _CACHED_IG_USER_ID
    if settings.INSTAGRAM_USER_ID:
        return settings.INSTAGRAM_USER_ID
    if _CACHED_IG_USER_ID:
        return _CACHED_IG_USER_ID

    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    if not token:
        return None

    version = settings.FACEBOOK_GRAPH_API_VERSION or "v17.0"
    url = f"https://graph.facebook.com/{version}/me"
    try:
        resp = requests.get(url, params={
            "fields": "instagram_business_account{id}",
            "access_token": token,
        }, timeout=15)
        data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        ig_biz = (data or {}).get("instagram_business_account") or {}
        ig_id = ig_biz.get("id")
        if ig_id:
            _CACHED_IG_USER_ID = ig_id
            return ig_id
    except Exception:
        pass

    return None


def publish_photo(image_url: str, caption: str) -> Tuple[bool, str]:
    """Publish a single photo to Instagram using the Graph API.

    Returns: (success, status_message)
    """
    token = settings.FACEBOOK_PAGE_ACCESS_TOKEN
    ig_user = _resolve_ig_user_id()
    if not token:
        return False, "Facebook access token not configured"
    if not ig_user:
        return False, "Could not resolve Instagram user ID from access token (is the Page linked to an Instagram professional account?)"

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
    ig_user = _resolve_ig_user_id()
    if not token:
        return False, "Facebook access token not configured"
    if not ig_user:
        return False, "Could not resolve Instagram user ID from access token (is the Page linked to an Instagram professional account?)"

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
    ig_user = _resolve_ig_user_id()
    if not token:
        return False, "Facebook access token not configured"
    if not ig_user:
        return False, "Could not resolve Instagram user ID from access token (is the Page linked to an Instagram professional account?)"

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
