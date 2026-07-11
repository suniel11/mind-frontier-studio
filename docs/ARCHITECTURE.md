# Mind Frontier Studio — Phase A Architecture

Phase A separates the application into four layers:

## API layer

`app/api/routes.py`

Owns HTTP endpoints, request validation, response models, and HTTP error mapping.

## Orchestration layer

`app/orchestration/project_pipeline.py`

Owns the complete production workflow:

1. Research
2. Script
3. Producer review
4. Character Bible
5. Storyboard
6. Narrative beats
7. Director decisions
8. Visual storytelling
9. Prompt compilation
10. Rendering
11. Quality inspection
12. Thumbnail generation
13. Release packaging
14. Studio Memory

## Core configuration

`app/core/settings.py`

Provides one authoritative root path, projects directory, static directory, application name, and version.

## Application entry point

`app/main.py`

Only configures FastAPI, static mounts, router registration, and the homepage.

## Benefits

- Removes duplicated project-root constants.
- Makes the production pipeline independently testable.
- Keeps HTTP concerns out of generation logic.
- Creates clear extension points for analytics, multi-channel presets, and batch production.
- Reduces future installer conflicts.
