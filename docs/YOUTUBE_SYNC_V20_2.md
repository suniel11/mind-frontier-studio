# YouTube Sync v20.2 — Video Library

v20.2 imports the connected channel's uploaded videos into Atlas.

## Imported fields

- Video ID
- Channel ID
- Title and description
- Thumbnail URL
- Publish date
- Duration
- Privacy status
- Category
- Tags
- Views
- Likes
- Comments
- Short/long-form classification
- Last synchronization time

## API

- `POST /api/youtube/sync-videos`
- `GET /api/youtube/videos`
- `GET /api/youtube/video-summary`

## Quota behavior

The sync uses the uploads playlist and batched `videos.list` calls. It does not use
the high-cost search endpoint.
