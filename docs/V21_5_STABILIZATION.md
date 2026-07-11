# Mind Frontier Studio v21.5 — Stabilization

## Added

- Versioned SQLite migrations
- Persistent background-job registry
- Job status and progress APIs
- Local backup creation and pruning
- Configuration validation
- Stability status endpoint
- Automated GitHub Actions tests

## API

- `GET /api/stability/status`
- `POST /api/stability/migrate`
- `GET /api/stability/jobs`
- `GET /api/stability/jobs/{job_id}`
- `POST /api/stability/backup`
- `POST /api/stability/backup/prune`

## Storage

- Database: `studio_memory/atlas.db`
- Backups: `studio_memory/backups/`
