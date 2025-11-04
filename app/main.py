# app/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.background import BackgroundScheduler
import os
import logging
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('app.log', encoding='utf-8')
    ]
)

# Create logger for main application
logger = logging.getLogger(__name__)

# Import routes
from app.routes import content, schedular
from app.routes import webhook
from app.routes import calendar_webhook
from app.routes import instagram_webhook

# Import services and config
from app.database import connection
from app.services import cleanup_service
from app.constants import CLEANUP_JOB_MINUTES
from app.config import settings  # <-- Import settings

# Initialize FastAPI app
app = FastAPI(title="Social Media Pipeline API")

# Add CORS middleware to allow requests from file:// (for local development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API Routers ---
# Register API routes BEFORE mounting the static files
app.include_router(content.router)
app.include_router(schedular.router)
app.include_router(webhook.router)
app.include_router(calendar_webhook.router)
app.include_router(instagram_webhook.router)


# --- Static Files Mount ---
# Mount frontend static files
frontend_dir = os.path.join(os.path.dirname(__file__), "frontend")
js_dir = os.path.join(frontend_dir, "js")

# Mount JS files first (to handle specific MIME type)
app.mount("/js", StaticFiles(directory=js_dir), name="javascript")

# Mount the root frontend LAST
# This serves the 'index.html' at the root URL
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# Initialize Background Scheduler
scheduler = BackgroundScheduler(timezone="UTC")

@app.on_event("startup")
def startup_event():
    logger.info("🚀 Starting Social Media Pipeline API server...")

    # 1. Check for critical configs
    if not settings.GOOGLE_STUDIO_API_KEY:
        logger.warning("⚠️  GOOGLE_STUDIO_API_KEY not found in .env file")
        logger.warning("   → Content generation will use mock data")
        logger.warning("   → Get a key from https://aistudio.google.com/app/apikey")
    else:
        logger.info("✅ Google AI Studio API key configured")

    # 2. Check for system prompts
    missing_prompts = []
    if not settings.STATIC_POST_PROMPT:
        missing_prompts.append("STATIC_POST_PROMPT")
    if not settings.CAROUSEL_POST_PROMPT:
        missing_prompts.append("CAROUSEL_POST_PROMPT")
    if not settings.VIDEO_POST_PROMPT:
        missing_prompts.append("VIDEO_POST_PROMPT")

    if missing_prompts:
        logger.warning("⚠️  Missing system prompts in .env file:")
        for prompt in missing_prompts:
            logger.warning(f"   → {prompt}")
        logger.warning("   → Content generation may not work as intended")
    else:
        logger.info("✅ All system prompts configured")

    # 3. Create database tables if they don't exist
    try:
        connection.create_tables()
        logger.info("✅ Database tables initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    # 4. Schedule the cleanup job
    try:
        scheduler.add_job(
            cleanup_service.check_and_delete_posts,
            'interval',
            minutes=CLEANUP_JOB_MINUTES,
            id='cleanup_job',
            name='Cleanup Old Posts'
        )
        logger.info(f"✅ Background cleanup scheduler started (every {CLEANUP_JOB_MINUTES} minutes)")
    except Exception as e:
        logger.error(f"❌ Failed to schedule cleanup job: {e}")

    # 5. Schedule the trigger job every minute
    try:
        scheduler.add_job(
            cleanup_service.check_and_trigger_posts,
            'interval',
            minutes=1,
            id='trigger_job',
            name='Trigger Scheduled Posts'
        )
        logger.info("✅ Background trigger scheduler started (every 1 minute)")
    except Exception as e:
        logger.error(f"❌ Failed to schedule trigger job: {e}")

    scheduler.start()
    logger.info("🎯 Server startup complete - ready to accept requests")

@app.on_event("shutdown")
def shutdown_event():
    logger.info("🛑 Shutting down Social Media Pipeline API server...")
    try:
        scheduler.shutdown()
        logger.info("✅ Background scheduler stopped successfully")
    except Exception as e:
        logger.error(f"❌ Error stopping scheduler: {e}")
    logger.info("👋 Server shutdown complete")

# Note: The lines for 'regenerate_media' and the duplicate 'app.mount'
# have been removed from here.

if __name__ == "__main__":
    import uvicorn
    logger.info("🌐 Starting Uvicorn server at http://127.0.0.1:8000")
    logger.info("📡 API documentation available at http://127.0.0.1:8000/docs")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True, log_level="info")
