from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
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
app.include_router(orion_router, prefix="/api")
app.include_router(atlas_router, prefix="/api")
app.include_router(producer_router, prefix="/api")


@app.get("/")
def home():
    return FileResponse(settings.static_dir / "index.html")
