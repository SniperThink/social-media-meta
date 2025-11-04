#!/usr/bin/env python3
"""
Script to start ngrok tunnel for local development.
This exposes localhost:8000 publicly for webhook testing.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pyngrok import ngrok
import time

def main():
    try:
        # Start ngrok tunnel
        print("Starting ngrok tunnel for localhost:8000...")
        public_url = ngrok.connect(8000)
        print(f"Ngrok tunnel established!")
        print(f"Public URL: {public_url}")
        print(f"Webhook URL: {public_url}/api/calendar/webhook")
        print("\nAdd this to your .env file:")
        print(f"CALENDAR_WEBHOOK_URL={public_url}/api/calendar/webhook")
        print("\nPress Ctrl+C to stop the tunnel...")

        # Keep the tunnel alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping ngrok tunnel...")
        ngrok.disconnect(public_url)
        ngrok.kill()
        print("Ngrok tunnel stopped.")

    except Exception as e:
        print(f"Error starting ngrok: {e}")
        print("Make sure you have ngrok installed and authenticated.")
        print("Run: ngrok authtoken YOUR_AUTH_TOKEN")

if __name__ == "__main__":
    main()
