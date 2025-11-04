#!/usr/bin/env python3
"""
Script to set up Google Calendar watch channel for push notifications.
This should be run once to establish the webhook connection.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.google_calender import setup_calendar_watch
from app.config import settings

def main():
    if not settings.CALENDAR_WEBHOOK_URL:
        print("ERROR: CALENDAR_WEBHOOK_URL not set in .env file")
        print("Please set CALENDAR_WEBHOOK_URL to your app's webhook endpoint")
        print("Example: CALENDAR_WEBHOOK_URL=https://your-app.com/api/calendar/webhook")
        return

    try:
        response = setup_calendar_watch(webhook_url=settings.CALENDAR_WEBHOOK_URL)
        print("Calendar watch channel set up successfully!")
        print(f"Channel ID: {response.get('id')}")
        print(f"Resource ID: {response.get('resourceId')}")
        print(f"Expiration: {response.get('expiration')}")
    except Exception as e:
        print(f"Failed to set up calendar watch: {e}")

if __name__ == "__main__":
    main()
