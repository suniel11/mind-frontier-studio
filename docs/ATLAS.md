# Project Atlas

Atlas is Mind Frontier Studio's local intelligence and analytics subsystem.

## What Atlas records

- Project title, topic, category, status and creation date
- Quality, Cinema and Producer scores
- Duration and engine version
- Publishing state
- YouTube views, likes, comments and subscribers gained
- Average percentage viewed
- Viewed-versus-swiped percentage
- Watch time, impressions and click-through rate when supplied

## Storage

Atlas uses SQLite from Python's standard library.

Database:

`studio_memory/atlas.db`

The database is excluded from Git by the existing `studio_memory/` rule.

## Learning behavior

Atlas does not fabricate performance predictions. When YouTube samples are missing,
it explicitly reports that more data is needed. Once metrics are supplied, it ranks
categories using observed views, retention and production quality.

## API

- `GET /api/atlas/dashboard`
- `GET /api/atlas/recommendations`
- `POST /api/atlas/sync`
- `POST /api/atlas/youtube-metrics`
- `PATCH /api/atlas/projects/{project_id}/status`
