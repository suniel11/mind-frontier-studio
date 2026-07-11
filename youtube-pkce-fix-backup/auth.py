from __future__ import annotations

import json
import secrets
from pathlib import Path
from typing import Any

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow


SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/yt-analytics.readonly",
]


def secrets_dir(root: Path) -> Path:
    path = root / ".secrets"
    path.mkdir(parents=True, exist_ok=True)
    return path


def client_secret_path(root: Path) -> Path:
    return root / "client_secret.json"


def token_path(root: Path) -> Path:
    return secrets_dir(root) / "youtube-token.json"


def state_path(root: Path) -> Path:
    return secrets_dir(root) / "youtube-oauth-state.json"


def credentials_exist(root: Path) -> bool:
    return client_secret_path(root).exists()


def load_credentials(root: Path) -> Credentials | None:
    path = token_path(root)
    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        credentials = Credentials.from_authorized_user_info(data, SCOPES)
    except (ValueError, OSError, json.JSONDecodeError):
        return None

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
        save_credentials(root, credentials)

    return credentials if credentials.valid else None


def save_credentials(root: Path, credentials: Credentials) -> None:
    token_path(root).write_text(
        credentials.to_json(),
        encoding="utf-8",
    )


def delete_credentials(root: Path) -> None:
    token_path(root).unlink(missing_ok=True)
    state_path(root).unlink(missing_ok=True)


def create_authorization_url(root: Path, redirect_uri: str) -> str:
    secret_file = client_secret_path(root)
    if not secret_file.exists():
        raise FileNotFoundError(
            "client_secret.json was not found in the Studio root folder."
        )

    flow = Flow.from_client_secrets_file(
        str(secret_file),
        scopes=SCOPES,
        redirect_uri=redirect_uri,
    )

    state = secrets.token_urlsafe(32)
    authorization_url, returned_state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )

    state_path(root).write_text(
        json.dumps(
            {
                "state": returned_state,
                "redirect_uri": redirect_uri,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return authorization_url


def complete_authorization(
    root: Path,
    authorization_response: str,
    received_state: str,
) -> Credentials:
    saved = json.loads(state_path(root).read_text(encoding="utf-8"))
    expected_state = str(saved.get("state", ""))
    redirect_uri = str(saved.get("redirect_uri", ""))

    if not expected_state or received_state != expected_state:
        raise ValueError("OAuth state validation failed.")

    flow = Flow.from_client_secrets_file(
        str(client_secret_path(root)),
        scopes=SCOPES,
        state=expected_state,
        redirect_uri=redirect_uri,
    )
    flow.fetch_token(authorization_response=authorization_response)

    credentials = flow.credentials
    save_credentials(root, credentials)
    state_path(root).unlink(missing_ok=True)
    return credentials


def connection_status(root: Path) -> dict[str, Any]:
    credentials = load_credentials(root)
    return {
        "client_secret_configured": credentials_exist(root),
        "connected": credentials is not None,
        "scopes": SCOPES,
        "token_path": str(token_path(root)),
    }
