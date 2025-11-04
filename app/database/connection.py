# app/database/connection.py
from app.config import settings

import psycopg2
import psycopg2.extras


def get_db_connection():
    """Return a psycopg2 connection using DATABASE_URL from settings."""
    if not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not set in configuration. Set it in .env or environment variables.")
    conn = psycopg2.connect(settings.DATABASE_URL)
    return conn


def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS scheduled_posts (
        id SERIAL PRIMARY KEY,
        post_type TEXT NOT NULL,
        selected_caption TEXT NOT NULL,
        scheduled_time TIMESTAMP NOT NULL,
        google_drive_folder_id TEXT,
        google_calendar_event_id TEXT,
        status TEXT NOT NULL DEFAULT 'scheduled',
        media_paths TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    cur.close()
    conn.close()
    print("Database tables checked/created.")


def execute_query(query: str, params: tuple = None, fetch: str = None):
    """
    Execute a query against Postgres and return results.
    - params: tuple of parameters
    - fetch: None | 'one' | 'all' to fetch results
    Returns dict for fetch='one' or list[dict] for fetch='all'.
    """
    params = params or ()
    conn = get_db_connection()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params)
        result = None
        if fetch == 'one':
            result = cur.fetchone()
        elif fetch == 'all':
            result = cur.fetchall()
        else:
            conn.commit()
        cur.close()
        return result
    finally:
        conn.close()