from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import ProjectRequest, ProjectOutput
from app.agents import character, research, script, storyboard, seo
from app.services.project_store import make_project_id, save_project
from app.services.media import build_video

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"

app = FastAPI(title="Mind Frontier Studio", version="2.2.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/projects", StaticFiles(directory=PROJECTS), name="projects")

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True, "version": "2.2.0"}

@app.post("/api/projects", response_model=ProjectOutput)
def create_project(request: ProjectRequest):
    try:
        research_result = research.run(request.topic)
        script_result = script.run(
            request.topic,
            research_result,
            request.target_seconds,
        )
        character_result = character.run(script_result)
        storyboard_result = storyboard.run(
            script_result,
            request.target_seconds,
            character_result,
        )
        seo_result = seo.run(script_result)

        project_id = make_project_id(request.topic)
        output = ProjectOutput(
            project_id=project_id,
            topic=request.topic,
            research=research_result,
            script=script_result,
            storyboard=storyboard_result,
            character_bible=character_result,
            seo=seo_result,
        )
        folder = save_project(output)

        video_path = build_video(folder, script_result, storyboard_result)
        output.video_url = f"/projects/{project_id}/{video_path.name}"
        save_project(output)
        return output
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
