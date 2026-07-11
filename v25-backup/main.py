from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.prediction.routes import router as prediction_router
from app.atlas_memory.routes import router as atlas_memory_router
from app.atlas_agents.routes import router as atlas_agents_router
from app.stability.routes import router as stability_router
from app.youtube_sync.routes import router as youtube_sync_router
from app.operations.routes import router as operations_router
from app.apollo.routes import router as apollo_router
from app.orion.routes import router as orion_router
from app.atlas.routes import router as atlas_router
from app.producer_ai.routes import router as producer_router
from app.core.settings import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.version,
)

app.mount(
    "/static",
    StaticFiles(directory=settings.static_dir),
    name="static",
)
app.mount(
    "/projects",
    StaticFiles(directory=settings.projects_dir),
    name="projects",
)

app.include_router(router)
app.include_router(prediction_router, prefix="/api")
app.include_router(atlas_memory_router, prefix="/api")
app.include_router(atlas_agents_router, prefix="/api")
app.include_router(stability_router, prefix="/api")
app.include_router(youtube_sync_router, prefix="/api")
app.include_router(operations_router, prefix="/api")
app.include_router(apollo_router, prefix="/api")
app.include_router(orion_router, prefix="/api")
app.include_router(atlas_router, prefix="/api")
app.include_router(producer_router, prefix="/api")


@app.get("/")
def home():
    return FileResponse(settings.static_dir / "index.html")
