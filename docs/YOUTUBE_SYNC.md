# YouTube Sync — Sprint 1

Sprint 1 adds secure local OAuth authentication and channel discovery.

## Google Cloud setup

Enable:

- YouTube Data API v3
- YouTube Analytics API

Create an OAuth client of type **Web application**.

Add this authorized redirect URI:

`http://127.0.0.1:8000/api/youtube/callback`

If your Studio opens as `localhost`, also add:

`http://localhost:8000/api/youtube/callback`

Download the OAuth client file and save it as:

`client_secret.json`

in the Studio root folder.

Do not commit this file. The repository `.gitignore` excludes it.

## Token storage

Refresh and access tokens are stored locally under:

`.secrets/youtube-token.json`

This directory is excluded from Git.

## API

- `GET /api/youtube/status`
- `POST /api/youtube/connect`
- `GET /api/youtube/callback`
- `POST /api/youtube/disconnect`
- `GET /api/youtube/channels`

## Scopes

Sprint 1 requests read-only access:

- `youtube.readonly`
- `yt-analytics.readonly`

Upload permission is deliberately not requested yet.
