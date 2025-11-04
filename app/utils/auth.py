# app/utils/auth.py
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from app.config import settings
from app.constants import SCOPES

def get_google_creds():
    """Authenticates with Google and returns credentials."""
    creds = None
    if os.path.exists(settings.GOOGLE_TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(settings.GOOGLE_TOKEN_FILE, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}. Re-authenticating...")
                creds = None
        
        if not creds:
            if not os.path.exists(settings.GOOGLE_CREDENTIALS_FILE):
                raise FileNotFoundError(
                    f"Credentials file not found: {settings.GOOGLE_CREDENTIALS_FILE}. "
                    "Please download it from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                settings.GOOGLE_CREDENTIALS_FILE, SCOPES
            )
            creds = flow.run_local_server(port=0)
        
        with open(settings.GOOGLE_TOKEN_FILE, "w") as token:
            token.write(creds.to_json())
            
    return creds