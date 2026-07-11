# Stability Release

This release adds structured pipeline observability and operational checks.

## Per-project diagnostics

Each project receives `pipeline-report.json`, containing stage timing and status.

JSONL logs are stored under:

`studio_memory/logs/`

## Health checks

`GET /api/operations/health`

Checks:

- OpenAI API key presence
- FFmpeg availability
- Writable project and memory directories
- Free disk space
- Required core modules

## Failure diagnostics

`GET /api/operations/recent-failures`

Returns recent failed stages with the project ID and underlying error.

## Error format

Pipeline failures now identify the exact stage, for example:

`render: FFmpeg scene rendering failed`

rather than returning only a generic 500 error.
