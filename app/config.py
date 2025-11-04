# app/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Google OAuth
    GOOGLE_CREDENTIALS_FILE: str = "credentials.json"
    GOOGLE_TOKEN_FILE: str = "token.json"
    
    # Database: use a full DATABASE_URL (Postgres-compatible) for production (Neon)
    DATABASE_URL: Optional[str] = None
    
    # Google AI Studio API Key
    GOOGLE_STUDIO_API_KEY: Optional[str] = None

    # System Prompts
    STATIC_POST_PROMPT: str = ""
    CAROUSEL_POST_PROMPT: str = ""
    VIDEO_POST_PROMPT: str = ""
    
    # Cloudflare R2 (S3-compatible) settings
    CLOUDFLARE_R2_ACCESS_KEY_ID: Optional[str] = None
    CLOUDFLARE_R2_SECRET_ACCESS_KEY: Optional[str] = None
    CLOUDFLARE_R2_ACCOUNT_ID: Optional[str] = None
    CLOUDFLARE_R2_BUCKET: Optional[str] = None
    CLOUDFLARE_R2_ENDPOINT: Optional[str] = None  # e.g. https://<account_id>.r2.cloudflarestorage.com
    CLOUDFLARE_R2_PUBLIC_URL: Optional[str] = None  # Public URL for accessing files, e.g. https://pub-xxx.r2.dev

    # Calendar Webhook URL for Google Calendar push notifications
    CALENDAR_WEBHOOK_URL: Optional[str] = None  # e.g. https://your-app.com/api/calendar/webhook

    # Facebook / Instagram (Graph API) configuration
    FACEBOOK_PAGE_ACCESS_TOKEN: Optional[str] = None  # Page access token used to publish to IG via Graph API
    INSTAGRAM_USER_ID: Optional[str] = None  # The IG Business/Creator Account ID
    FACEBOOK_GRAPH_API_VERSION: str = "v17.0"
    FACEBOOK_WEBHOOK_VERIFY_TOKEN: Optional[str] = None  # Verify token for webhook verification
    FACEBOOK_APP_SECRET: Optional[str] = None  # App secret for signature verification
    
    class Config:
        env_file = ".env"

settings = Settings()