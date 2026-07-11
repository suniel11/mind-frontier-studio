# Mind Frontier Studio v27 — Autonomous Orchestrator

v27 connects Atlas Memory, YouTube evidence, specialist agents, prediction, and workspace storage into one workflow.

## One-command workflow

1. Rebuild Atlas Memory
2. Search topic memory
3. Run Research Agent
4. Run Producer Agent
5. Run Thumbnail Agent
6. Run Publishing Agent
7. Run Prediction Engine
8. Calculate readiness and confidence
9. Save a Producer Workspace
10. Persist the execution graph

## Reliability

Each specialist stage is recorded with:

- Status
- Duration
- Output
- Error
- Fallback result

## API

- `POST /api/orchestrator/create-project`
- `GET /api/orchestrator/projects`
- `GET /api/orchestrator/project/{project_id}`
- `POST /api/orchestrator/regenerate/{project_id}`
- `POST /api/orchestrator/finalize`
