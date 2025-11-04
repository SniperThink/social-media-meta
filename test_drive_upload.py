#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.google_drive import upload_files_to_drive

def test_upload():
    # Test with local files instead of URLs since network might be blocked
    test_files = [
        "app/frontend/temp_generated_images/0fc04c3e-9696-4e36-b3c3-58ff215ea7c0.png",  # Existing PNG
        "app/frontend/temp_generated_images/8d0b27ba-30cc-4198-9091-ea7c0d557672.jpg"   # Existing JPG
    ]
    caption = "Test caption for upload"

    try:
        folder_id, uploaded_media = upload_files_to_drive(test_files, caption, post_type="test")
        print(f"Test successful! Folder ID: {folder_id}")
        for media in uploaded_media:
            print(f"Uploaded: {media['file_name']} (ID: {media['uploaded_file_id']}, MIME: {media['mime_type']})")
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_upload()
    sys.exit(0 if success else 1)
