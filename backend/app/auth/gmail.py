from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from app.config import settings


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.compose",
]


def authorize_gmail() -> Path:
    credentials_path = settings.gmail_credentials_path
    token_path = settings.gmail_token_path
    if not credentials_path.is_file():
        raise FileNotFoundError(
            f"Google OAuth credentials were not found at {credentials_path.resolve()}."
        )

    token_path.parent.mkdir(parents=True, exist_ok=True)
    flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
    credentials = flow.run_local_server(host="localhost", port=0, open_browser=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return token_path


def load_gmail_credentials() -> Credentials:
    token_path = settings.gmail_token_path
    if not token_path.is_file():
        raise RuntimeError("Gmail is not connected. Run uv run python -m app.auth.gmail.")

    credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if not credentials.valid:
        if not credentials.expired or not credentials.refresh_token:
            raise RuntimeError("Gmail authorization expired. Reconnect the Gmail account.")
        credentials.refresh(Request())
        token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


if __name__ == "__main__":
    path = authorize_gmail()
    print(f"Gmail connected. Token saved at {path.resolve()}.")
