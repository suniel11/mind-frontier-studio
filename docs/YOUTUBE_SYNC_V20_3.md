# YouTube Sync v20.3 — Project Matching

v20.3 links Mind Frontier Studio projects to imported YouTube videos.

## Matching logic

Candidate scores combine:

- Normalized title similarity
- Topic keyword overlap

## Capabilities

- Suggested matches
- High-confidence automatic matching
- Manual matching
- Unmatching
- Match summary
- Published-project status updates
- Match event history in Atlas

## API

- `GET /api/youtube/match-suggestions`
- `POST /api/youtube/match`
- `POST /api/youtube/auto-match`
- `DELETE /api/youtube/match/{video_id}`
- `GET /api/youtube/match-summary`
