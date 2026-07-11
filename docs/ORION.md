# Project Orion

Orion is Mind Frontier Studio's autonomous single-project production layer.

## Workflow

1. Enter a high-level production objective.
2. Orion consults the Content Planner, AI Producer, recent project memory and Atlas.
3. It creates a ranked mission of one to five candidate videos.
4. Review the candidate scores and reasons.
5. Produce only the approved item.
6. Orion runs the existing full production pipeline and records the resulting project.

## Cost protection

Orion does not automatically render all planned videos. Every candidate requires an
explicit **Produce This** action. Planning is local and does not consume OpenAI credits.

## Storage

Mission files are stored under:

`studio_memory/orion-missions/`

## API

- `POST /api/orion/plan`
- `GET /api/orion/missions`
- `GET /api/orion/missions/{mission_id}`
- `POST /api/orion/missions/{mission_id}/execute`
