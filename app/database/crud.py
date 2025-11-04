# app/database/crud.py
from app.database.connection import execute_query
import datetime
import json

def add_scheduled_post(post_type, caption, scheduled_time, folder_id, event_id, media_paths=None):
    """
    Adds a scheduled post record. `media_paths` should be a list of uploaded media metadata
    (e.g. [{requested_path, r2_url, uploaded_file_id, file_name, mime_type}, ...]) so the DB stores
    canonical identifiers (R2 URLs, Drive file ids) rather than ephemeral local paths.
    """
    media_paths_json = json.dumps(media_paths) if media_paths else None
    query = '''
    INSERT INTO scheduled_posts (post_type, selected_caption, scheduled_time, google_drive_folder_id, google_calendar_event_id, media_paths)
    VALUES (%s, %s, %s, %s, %s, %s)
    '''
    execute_query(query, (post_type, caption, scheduled_time, folder_id, event_id, media_paths_json))

def find_posts_for_deletion(delay_hours: int):
    """Finds posts whose scheduled_time was more than delay_hours ago."""
    threshold_time = datetime.datetime.now() - datetime.timedelta(hours=delay_hours)
    query = '''
    SELECT * FROM scheduled_posts
    WHERE scheduled_time < %s AND status = 'scheduled'
    '''
    rows = execute_query(query, (threshold_time,), fetch='all')
    return rows or []

def find_posts_to_trigger():
    """Finds posts whose scheduled_time has arrived and status is 'scheduled'.

    Development modification: Only trigger posts scheduled within the last minute to prioritize realtime.
    This skips older posts for now in development.

    To undo this change and revert to triggering all past-due posts:
    - Replace the query with:
      SELECT * FROM scheduled_posts
      WHERE scheduled_time <= %s AND status = 'scheduled'
    - Remove the ORDER BY clause.
    - Change the execute_query call to: execute_query(query, (now,), fetch='all')
    - Remove the now_minus_one calculation.
    """
    from datetime import datetime, timedelta
    now = datetime.now()
    now_minus_one = now - timedelta(minutes=1)
    query = '''
    SELECT * FROM scheduled_posts
    WHERE scheduled_time >= %s AND scheduled_time <= %s AND status = 'scheduled'
    ORDER BY scheduled_time ASC
    '''
    rows = execute_query(query, (now_minus_one, now), fetch='all')
    return rows or []

def update_post_status(post_id: int, new_status: str):
    query = '''
    UPDATE scheduled_posts
    SET status = %s
    WHERE id = %s
    '''
    execute_query(query, (new_status, post_id))

def cancel_post_by_event_id(event_id: str):
    """Cancels a scheduled post by marking it as 'cancelled' when the corresponding calendar event is deleted."""
    query = '''
    UPDATE scheduled_posts
    SET status = 'cancelled'
    WHERE google_calendar_event_id = %s AND status = 'scheduled'
    '''
    execute_query(query, (event_id,))
