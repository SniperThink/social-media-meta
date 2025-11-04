# app/constants.py
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/calendar"
]

# Delay in hours after the scheduled time to delete the folder
DELETE_DELAY_HOURS = 1

# How often the cleanup job checks for old posts
CLEANUP_JOB_MINUTES = 15