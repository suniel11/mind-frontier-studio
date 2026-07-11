from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.core.settings import settings
from app.youtube_sync.auth import (
    complete_authorization,
    connection_status,
    create_authorization_url,
    delete_credentials,
)
from app.youtube_sync.service import get_channels
from app.youtube_sync.video_sync import sync_video_library
from app.youtube_sync.video_store import list_videos, video_summary
from app.youtube_sync.channel_sync import sync_channels, stored_channels

router = APIRouter(prefix="/youtube", tags=["YouTube Sync"])


def callback_url(request: Request) -> str:
    return str(request.url_for("youtube_oauth_callback"))


@router.get("/status")
def youtube_status():
    result = connection_status(settings.root)

    if result["connected"]:
        try:
            result["channels"] = get_channels(settings.root)
        except Exception as exc:
            result["connected"] = False
            result["connection_error"] = str(exc)
            result["channels"] = []
    else:
        result["channels"] = []

    return result


@router.post("/connect")
def youtube_connect(request: Request):
    try:
        url = create_authorization_url(
            settings.root,
            callback_url(request),
        )
        return {
            "authorization_url": url,
            "redirect_uri": callback_url(request),
        }
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/callback", name="youtube_oauth_callback")
def youtube_oauth_callback(
    request: Request,
    state: str,
):
    try:
        complete_authorization(
            settings.root,
            str(request.url),
            state,
        )
    except Exception as exc:
        return HTMLResponse(
            content=(
                "<h2>YouTube connection failed</h2>"
                f"<p>{str(exc)}</p>"
                "<p>You can close this tab and return to Mind Frontier Studio.</p>"
            ),
            status_code=400,
        )

    return HTMLResponse(
        content=(
            "<h2>YouTube connected successfully</h2>"
            "<p>You can close this tab and return to Mind Frontier Studio.</p>"
            "<script>setTimeout(() => window.close(), 1500);</script>"
        )
    )


@router.post("/disconnect")
def youtube_disconnect():
    delete_credentials(settings.root)
    return {"ok": True, "connected": False}


@router.get("/channels")
def youtube_channels():
    try:
        return {"channels": get_channels(settings.root)}
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/sync-channel")
def youtube_sync_channel():
    try:
        return sync_channels(settings.root)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/stored-channels")
def youtube_stored_channels():
    return {"channels": stored_channels(settings.root)}


@router.post("/sync-videos")
def youtube_sync_videos():
    try:
        return sync_video_library(settings.root)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/videos")
def youtube_videos(
    limit: int = 100,
    offset: int = 0,
    search: str = "",
    short_only: bool | None = None,
):
    return {
        "videos": list_videos(
            settings.root,
            limit=limit,
            offset=offset,
            search=search,
            short_only=short_only,
        )
    }


@router.get("/video-summary")
def youtube_video_summary():
    return video_summary(settings.root)
