<<<<<<< HEAD
# Social Media Automation API - The Bible

## Overview

The **Social Media Automation API** is a comprehensive, AI-powered tool designed to streamline the creation, scheduling, and publishing of social media content. Built with **FastAPI**, this application leverages **Google Gemini AI** for generating high-quality posts (static images, carousels, and videos), integrates with **Google Drive** and **Google Calendar** for organization and scheduling, and publishes directly to Instagram using the **Facebook Graph API**. It also utilizes **Cloudflare R2** for reliable media storage and retrieval.

This "Bible" README serves as the ultimate guide to understanding, setting up, and using the project. Whether you're a developer contributing to the codebase or an end-user deploying it, this document covers everything from architecture to troubleshooting.

### Key Technologies
- **Backend**: FastAPI (Python async web framework)
- **AI Generation**: Google Gemini AI (via `google-generativeai` and `google-genai`)
- **Storage**: Cloudflare R2 (S3-compatible), Google Drive
- **Scheduling**: Google Calendar, APScheduler for background tasks
- **Database**: PostgreSQL-compatible (e.g., Neon.tech)
- **Authentication**: Google OAuth 2.0
- **Publishing**: Facebook Graph API for Instagram (photos, carousels, videos)
- **Frontend**: Static HTML/CSS/JS served by FastAPI
- **Deployment**: Uvicorn for ASGI server

### Project Structure
```
d:/SniperThinkProjects/Social Media Automation/
├── app/
│   ├── config.py                 # Pydantic settings for environment variables
│   ├── constants.py              # App constants (e.g., cleanup intervals)
│   ├── main.py                   # FastAPI app initialization, routes, and scheduler
│   ├── database/
│   │   ├── connection.py         # Database connection and table creation
│   │   └── crud.py               # CRUD operations for scheduled posts
│   ├── frontend/
│   │   ├── index.html            # Main UI
│   │   ├── css/styles.css        # Styles
│   │   ├── js/
│   │   │   ├── api.js            # API client logic
│   │   │   └── main.js           # Frontend interactions
│   │   └── temp_generated_images/ # Temp storage for generated media
│   ├── models/
│   │   └── schemas.py            # Pydantic models for requests/responses
│   ├── routes/
│   │   ├── content.py            # Content generation endpoints
│   │   ├── schedular.py          # Scheduling endpoints
│   │   └── webhook.py            # Webhook for external publishing
│   ├── services/
│   │   ├── cleanup_service.py    # Background cleanup of old posts
│   │   ├── facebook_graph.py     # Facebook Graph API (Instagram publishing)
│   │   ├── generator_service.py  # AI content generation
│   │   ├── google_calender.py    # Google Calendar integration
│   │   ├── google_drive.py       # Google Drive uploads
│   │   ├── publisher_service.py  # Media publishing helpers
│   │   └── r2_service.py         # Cloudflare R2 storage
│   └── utils/
│       ├── auth.py               # OAuth utilities
│       └── retry.py              # Retry decorator for resilience
├── scripts/
│   └── test_neon_connection.py   # DB connection test script
├── credentials.json              # Google OAuth credentials
├── token.json                    # OAuth tokens
├── requirements.txt              # Python dependencies
├── .env                          # Environment variables (not committed)
└── README.md                     # This file
```

## Features

- **Content Generation**:
  - Generate static posts, carousels, and videos using AI prompts.
  - Supports regeneration of individual media or captions.
  - Uses customizable system prompts for tailored output.

- **Scheduling & Organization**:
  - Upload generated media to Google Drive folders.
  - Create Google Calendar events for scheduled posts.
  - Persist schedules in a database for tracking.

- **Publishing & Integration**:
  - Direct Instagram publishing via Facebook Graph API (photos, carousels, videos).
  - Media validation and preparation (JPEG conversion, aspect ratio adjustments for Instagram).
  - Fallback mechanisms for media retrieval (R2 > Drive > HTTP).
  - Webhook endpoint for external scheduling requests.

- **Storage & Reliability**:
  - Cloudflare R2 for public media hosting.
  - Background cleanup of temporary files and old posts.
  - Retry logic for transient failures (e.g., API calls).

- **Frontend**:
  - Simple web UI for interacting with the API.
  - Served statically by FastAPI.

- **Security & Config**:
  - Environment-based configuration (.env file).
  - Google OAuth for Drive/Calendar access.
  - Facebook Graph API with Page access tokens for Instagram publishing.
  - CORS enabled for local development.

## Installation

### Prerequisites
- Python 3.8+
- A Google Cloud Project with APIs enabled: Google Drive API, Google Calendar API, AI Studio API.
- Facebook Page with Instagram Business/Creator account linked (for Graph API publishing).
- Page access token with Instagram publishing permissions (instagram_content_publish, instagram_basic, pages_manage_posts).
- Cloudflare R2 account (optional, for media storage).
- PostgreSQL database (e.g., Neon.tech for serverless).

### Steps
1. **Clone or Download the Project**:
   - Ensure you're in the project directory: `d:/SniperThinkProjects/Social Media Automation`.

2. **Set Up Virtual Environment**:
   ```
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

3. **Install Dependencies**:
   ```
   pip install -r requirements.txt
   ```

4. **Configure Environment**:
   - Copy `.env.example` to `.env` and fill in your values.
   - Key variables to set (see `.env.example` for full list):
     ```
     DATABASE_URL=postgresql://user:pass@host/db
     GOOGLE_STUDIO_API_KEY=your_google_ai_api_key
     
     # Facebook/Instagram Graph API
     FACEBOOK_PAGE_ACCESS_TOKEN=your_page_access_token
     INSTAGRAM_USER_ID=your_instagram_business_account_id
     FACEBOOK_GRAPH_API_VERSION=v17.0
     
     # System prompts for AI generation
     STATIC_POST_PROMPT=Your prompt for static posts
     CAROUSEL_POST_PROMPT=Your prompt for carousels
     VIDEO_POST_PROMPT=Your prompt for videos
     
     # Optional: Cloudflare R2 for media storage
     CLOUDFLARE_R2_ACCESS_KEY_ID=your_r2_key
     CLOUDFLARE_R2_SECRET_ACCESS_KEY=your_r2_secret
     CLOUDFLARE_R2_ACCOUNT_ID=your_account_id
     CLOUDFLARE_R2_BUCKET=your_bucket
     CLOUDFLARE_R2_ENDPOINT=https://your_account_id.r2.cloudflarestorage.com
     CLOUDFLARE_R2_PUBLIC_URL=https://pub-xxx.r2.dev
     ```
   - Place `credentials.json` (from Google Cloud) in the root.

5. **Run Database Setup**:
   - The app auto-creates tables on startup, but test with:
     ```
     python scripts/test_neon_connection.py
     ```

6. **Start the Server**:
   ```
   python app/main.py
   ```
   - Access at `http://127.0.0.1:8000`.
   - Frontend loads at root; API docs at `/docs`.

## Configuration

All settings are managed via `app/config.py` using Pydantic. Key configs:

- **Google OAuth**: `credentials.json` and `token.json` for Drive/Calendar.
- **Facebook/Instagram**: `FACEBOOK_PAGE_ACCESS_TOKEN` and `INSTAGRAM_USER_ID` for Graph API publishing.
- **AI Prompts**: Customize in `.env` for different post types.
- **Storage**: R2 settings for media uploads (optional but recommended).
- **Database**: Full URL for Postgres.
- **Cleanup**: Interval in `app/constants.py` (default: 15 minutes).

Warnings are logged on startup if critical configs (e.g., API keys) are missing.

## Usage

### Frontend
- Open `http://127.0.0.1:8000` in a browser.
- Use the UI to generate content, select media, and schedule posts.

### API Endpoints

#### Content Generation
- `POST /api/content/generate`: Generate posts.
  - Body: `{"prompt": "string", "post_type": "static|carousel|video", "num_media": int}`
  - Response: Generated content with media URLs and captions.

- `POST /api/content/regenerate`: Regenerate specific items.
  - Body: `{"prompt": "string", "post_type": "string", "index": int, "media": [...], "regen_target": "media|caption"}`

#### Scheduling
- `POST /api/schedule/`: Schedule a post.
  - Body: `{"selected_media": [...], "selected_caption": "string", "post_type": "string", "scheduled_time": "ISO datetime", "timezone": "string"}`
  - Uploads to Drive, creates Calendar event, saves to DB.

#### Webhook
- `POST /api/webhook/schedule`: External scheduling with media prep and Instagram publishing.
  - Handles R2/Drive media, validates for Instagram, publishes via Graph API.
  - Supports carousel endpoints: `/api/webhook/carousel_2` through `/api/webhook/carousel_10`.

Full API docs available at `/docs` (Swagger UI).

### Background Tasks
- **Cleanup**: Runs every 15 minutes, deleting old temp files and DB records.
- **Trigger**: Runs every 1 minute, checking for scheduled posts that are due and publishing them to Instagram via Graph API.

## Troubleshooting

- **AI Generation Fails**: Check `GOOGLE_STUDIO_API_KEY` and prompts in `.env`.
- **OAuth Errors**: Re-run OAuth flow; ensure `credentials.json` is valid.
- **DB Issues**: Verify `DATABASE_URL`; use Neon dashboard for logs.
- **R2 Uploads Fail**: Confirm R2 credentials and bucket permissions.
- **Instagram Publishing Fails**: 
  - Verify `FACEBOOK_PAGE_ACCESS_TOKEN` is valid and has required permissions.
  - Ensure `INSTAGRAM_USER_ID` is correct (Business/Creator account ID, not Page ID).
  - Check that media URLs are publicly accessible (Graph API needs to download them).
  - For videos, ensure they meet Instagram requirements (format, duration, size).
- **Frontend Not Loading**: Ensure static files are mounted; check browser console.

Logs are printed to console; enable debug mode in Uvicorn for more.

## Contributing

1. Fork the repo.
2. Create a feature branch: `git checkout -b feature/your-feature`.
3. Make changes, test thoroughly.
4. Submit a PR with a clear description.

- Follow PEP 8 for Python code.
- Update this README for any new features.
- Test with `python -m pytest` (if tests are added).

## License

This project is licensed under the MIT License. See LICENSE file for details.

## Changelog

- **v1.0**: Initial release with core generation, scheduling, and webhook features.
- **v2.0**: Added R2 storage, improved media validation, and Instagram prep.
- **v3.0**: Replaced Make.com webhooks with direct Facebook Graph API publishing for Instagram.

For questions, open an issue or contact the maintainer.
=======
# social-media-with-meta
>>>>>>> origin/main
