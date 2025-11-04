# app/models/schemas.py
from pydantic import BaseModel
from typing import List, Optional, Any, Dict

class GenerateRequest(BaseModel):
    prompt: str
    post_type: str  # 'static', 'carousel', 'video'
    num_media: int

class GenerateResponse(BaseModel):
    media: List[str]
    captions: List[str]

class ScheduleRequest(BaseModel):
    selected_media: List[str]
    selected_caption: str
    scheduled_time: str  # ISO format from datetime-local input
    post_type: str
    timezone: str | None = None

class ScheduleResponse(BaseModel):
    message: str
    folder_id: str
    event_id: str
    webhook_sent: bool = False
    webhook_status: Optional[str] = None


class MediaEntry(BaseModel):
    requested_path: Optional[str] = None
    r2_url: Optional[str] = None
    uploaded_file_id: Optional[str] = None
    file_name: Optional[str] = None
    mime_type: Optional[str] = None


class WebhookRequest(BaseModel):
    media: List[MediaEntry]
    selected_caption: str
    scheduled_time: str
    post_type: str
    timezone: Optional[str] = None


class WebhookResponse(BaseModel):
    message: str
    folder_id: str
    event_id: str
    webhook_sent: bool = False
    webhook_status: Optional[str] = None


class RegenerateRequest(BaseModel):
    prompt: str
    post_type: str  # 'static', 'carousel', 'video'
    index: int
    media: List[str] = []
    regen_target: str  # 'media' or 'caption'
    captions: List[str] = []  # Add current captions to avoid duplicates


class RegenerateResponse(BaseModel):
    media_url: Optional[str] = None
    caption: Optional[str] = None
    captions: Optional[List[str]] = None

class UpdateCaptionRequest(BaseModel):
    index: int
    new_caption: str

class UpdateCaptionResponse(BaseModel):
    success: bool
    message: str


# Instagram Webhook Schemas
class InstagramWebhookEntry(BaseModel):
    id: str
    time: int
    changes: List[Dict[str, Any]]  # Flexible for different event types


class InstagramWebhookValue(BaseModel):
    # Common fields for media events
    id: Optional[str] = None
    media_id: Optional[str] = None
    permalink: Optional[str] = None
    media_url: Optional[str] = None
    caption: Optional[str] = None
    timestamp: Optional[str] = None
    # For comments
    comment_id: Optional[str] = None
    text: Optional[str] = None
    from_user: Optional[Dict[str, Any]] = None
    # Generic field for other data
    additional_data: Optional[Dict[str, Any]] = None


class InstagramWebhookChange(BaseModel):
    field: str  # e.g., "media", "comments"
    value: InstagramWebhookValue


class InstagramWebhookRequest(BaseModel):
    object: str  # Should be "instagram"
    entry: List[InstagramWebhookEntry]
