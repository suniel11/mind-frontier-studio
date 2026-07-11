# YouTube Sync v20.4 — Dashboard and Incremental Sync

v20.4 completes the first YouTube synchronization milestone.

## Incremental sync

The incremental mode:

- Reads the uploads playlist from newest to oldest
- Stops after encountering several known videos
- Refreshes statistics for the newest imported videos
- Uses batched `videos.list` calls
- Avoids the expensive search endpoint

Full sync remains available when the complete library must be rebuilt.

## Dashboard

The dashboard includes:

- Live channel totals
- Imported video totals
- Shorts and long-form split
- Total and average views
- Matched and unmatched counts
- Recent uploads
- Top videos
- Last synchronization result

## API

- `POST /api/youtube/sync-library`
- `GET /api/youtube/dashboard`
