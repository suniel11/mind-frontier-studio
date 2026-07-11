from __future__ import annotations

import json
import random
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
VALID_PRIVACY = {"private", "unlisted", "public"}
RETRIABLE_STATUS_CODES = {500, 502, 503, 504}
MAX_RETRIES = 8


@dataclass
class YouTubeUploadResult:
    video_id: str
    url: str
    privacy_status: str
    title: str
    scheduled_publish_at: str | None
    thumbnail_uploaded: bool

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _load_credentials(
    client_secrets_path: Path,
    token_path: Path,
) -> Credentials:
    credentials: Credentials | None = None

    if token_path.exists():
        credentials = Credentials.from_authorized_user_file(
            str(token_path),
            [YOUTUBE_UPLOAD_SCOPE],
        )

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        if not client_secrets_path.exists():
            raise FileNotFoundError(
                f"OAuth client file not found: {client_secrets_path}"
            )

        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secrets_path),
            scopes=[YOUTUBE_UPLOAD_SCOPE],
        )
        credentials = flow.run_local_server(
            port=0,
            access_type="offline",
            prompt="consent",
            open_browser=True,
            success_message=(
                "Mind Frontier Studio is connected to YouTube. "
                "You can close this browser tab."
            ),
        )

    token_path.parent.mkdir(parents=True, exist_ok=True)
    token_path.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


def _build_youtube(
    client_secrets_path: Path,
    token_path: Path,
):
    credentials = _load_credentials(client_secrets_path, token_path)
    return build(
        "youtube",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )


def _execute_resumable(request) -> dict[str, Any]:
    response = None
    retry_count = 0

    while response is None:
        try:
            _, response = request.next_chunk()
            if response is not None and "id" not in response:
                raise RuntimeError(
                    f"Unexpected YouTube upload response: {response}"
                )
        except HttpError as exc:
            status = getattr(exc.resp, "status", None)
            if status not in RETRIABLE_STATUS_CODES:
                raise

            retry_count += 1
            if retry_count > MAX_RETRIES:
                raise RuntimeError(
                    "YouTube upload failed after repeated retries."
                ) from exc

            sleep_seconds = random.random() * (2 ** retry_count)
            time.sleep(sleep_seconds)

    return response


def _normalize_tags(values: list[str]) -> list[str]:
    tags: list[str] = []
    for value in values:
        cleaned = value.strip().lstrip("#").strip()
        if cleaned and cleaned not in tags:
            tags.append(cleaned)
    return tags[:30]


def upload_release(
    project_dir: Path,
    client_secrets_path: Path,
    token_path: Path,
    privacy_status: str = "private",
    publish_at: str | None = None,
    category_id: str = "27",
) -> YouTubeUploadResult:
    project_dir = project_dir.resolve()
    package_path = project_dir / "release-package.json"

    if not package_path.exists():
        raise FileNotFoundError(
            f"Release package not found: {package_path}"
        )

    package = json.loads(package_path.read_text(encoding="utf-8"))

    video_path = Path(package["video_path"])
    thumbnail_path = Path(package["thumbnail_path"])

    if not video_path.is_absolute():
        video_path = project_dir / video_path
    if not thumbnail_path.is_absolute():
        thumbnail_path = project_dir / thumbnail_path

    if not video_path.exists():
        fallback = project_dir / "mind-frontier-short.mp4"
        if fallback.exists():
            video_path = fallback
        else:
            raise FileNotFoundError(f"Video not found: {video_path}")

    if privacy_status not in VALID_PRIVACY:
        raise ValueError(
            f"privacy_status must be one of: {sorted(VALID_PRIVACY)}"
        )

    status_body: dict[str, Any] = {
        "privacyStatus": privacy_status,
        "selfDeclaredMadeForKids": False,
    }

    if publish_at:
        # YouTube scheduling requires a private video.
        status_body["privacyStatus"] = "private"
        status_body["publishAt"] = publish_at

    hashtags = package.get("hashtags", [])
    description = package.get("description", "").strip()
    if hashtags:
        description = f"{description}\n\n{' '.join(hashtags)}".strip()

    youtube = _build_youtube(
        client_secrets_path=client_secrets_path,
        token_path=token_path,
    )

    body = {
        "snippet": {
            "title": package.get("title", "Mind Frontier"),
            "description": description,
            "tags": _normalize_tags(hashtags),
            "categoryId": category_id,
        },
        "status": status_body,
    }

    upload_request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=MediaFileUpload(
            str(video_path),
            chunksize=8 * 1024 * 1024,
            resumable=True,
        ),
    )

    response = _execute_resumable(upload_request)
    video_id = response["id"]

    thumbnail_uploaded = False
    if thumbnail_path.exists():
        try:
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(
                    str(thumbnail_path),
                    resumable=False,
                ),
            ).execute()
            thumbnail_uploaded = True
        except HttpError:
            # The video upload succeeded; keep that result even if the
            # thumbnail endpoint is unavailable for the channel.
            thumbnail_uploaded = False

    result = YouTubeUploadResult(
        video_id=video_id,
        url=f"https://www.youtube.com/watch?v={video_id}",
        privacy_status=status_body["privacyStatus"],
        title=body["snippet"]["title"],
        scheduled_publish_at=publish_at,
        thumbnail_uploaded=thumbnail_uploaded,
    )

    (project_dir / "youtube-upload.json").write_text(
        json.dumps(result.model_dump(), indent=2),
        encoding="utf-8",
    )
    return result
