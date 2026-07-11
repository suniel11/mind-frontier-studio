# Mind Frontier Studio v21 — Atlas Intelligence

v21 adds YouTube Analytics synchronization and evidence-based channel analysis.

## Metrics

- Views
- Estimated minutes watched
- Average view duration
- Average percentage viewed
- Subscribers gained
- Likes
- Comments
- Shares

## Intelligence

- Topic performance
- Hook-type performance from matched project scripts
- Publishing day and hour summaries
- Growth totals and daily history
- Evidence-based recommendations
- Explicit sample-size and causality limitations

## API

- `POST /api/youtube/sync-analytics`
- `GET /api/youtube/intelligence`

## Deliberate limitation

Impressions and thumbnail CTR are not included because they are not exposed through
the same general targeted Analytics query used for the supported metrics above.
