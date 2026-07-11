# Mind Frontier Studio v24 — Prediction Engine

v24 forecasts likely Short performance using the creator's own historical data.

## Forecasts

- Views range
- Average percentage viewed
- Subscriber gain range
- Confidence
- Risk level
- Comparable historical videos
- Runtime, hook, and publishing factors

## Learning loop

After the video has real results, actual metrics can be attached to the prediction.
The calibration report measures forecast error over time.

## API

- `POST /api/prediction/forecast`
- `POST /api/prediction/review`
- `GET /api/prediction/history`
- `GET /api/prediction/calibration`

## Important limitation

This release uses an evidence-weighted heuristic, not a guaranteed machine-learning
forecast. Predictions become more credible only when enough matched videos and
Analytics data exist.
