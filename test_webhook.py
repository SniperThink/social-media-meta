import requests
import json
import sys
import os

# Add the app directory to the path to import MAKE_WEBHOOK_URLS
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from routes.webhook import MAKE_WEBHOOK_URLS

# Test carousel_3 webhook payload with 3 images
payload = {
    "folder_id": "test_folder_id",
    "event_id": "test_event_id",
    "post_type": "carousel_3",
    "scheduled_time": "2023-10-27T12:00:00",
    "caption": "Test carousel caption",
    "photo_url_1": "https://example.com/image1.jpg",
    "photo_url_2": "https://example.com/image2.jpg",
    "photo_url_3": "https://example.com/image3.jpg"
}

# Send request directly to Make webhook URL for carousel_3
webhook_url = MAKE_WEBHOOK_URLS['carousel_3']
response = requests.post(
    webhook_url,
    json=payload,
    headers={"Content-Type": "application/json"}
)

print(f"Webhook URL: {webhook_url}")
print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
