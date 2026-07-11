from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.models import ProjectRequest, ProjectOutput
from app.agents import character, research, script, storyboard, seo
from app.services.project_store import make_project_id, save_project
from app.services.media import build_video
from app.producer.review import review_script
from app.editor.planner import apply_edit_plan
from app.quality.inspector import inspect_project
from app.learning.memory import record_project
from app.learning.profile import load_studio_profile, save_studio_profile
from app.visual.pipeline import apply_visual_storytelling
from app.director.engine import apply_director_engine
from app.publishing.thumbnail import create_thumbnail, choose_thumbnail_source
from app.publishing.release import build_release_package
from app.publishing.manifest import write_release_manifest
from app.production.pipeline import compile_storyboard_prompts

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "projects"

app = FastAPI(title="Mind Frontier Studio", version="7.0.0")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/projects", StaticFiles(directory=PROJECTS), name="projects")

@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")

@app.get("/api/health")
def health():
    return {"ok": True, "version": "7.0.0"}

@app.post("/api/projects", response_model=ProjectOutput)
def create_project(request: ProjectRequest):
    try:
        research_result = research.run(request.topic)
        script_result = script.run(
            request.topic,
            research_result,
            request.target_seconds,
        )
        producer_result = review_script(script_result)
        if not producer_result.approved:
            raise RuntimeError(
                "Producer review rejected the script: "
                + " ".join(producer_result.notes)
            )
        character_result = character.run(script_result)
        storyboard_result = storyboard.run(
            script_result,
            request.target_seconds,
            character_result,
        )
        storyboard_result = apply_edit_plan(
            storyboard_result,
            request.target_seconds,
        )
        studio_profile = load_studio_profile(ROOT)
        storyboard_result, director_plan = apply_director_engine(
            storyboard_result,
            studio_profile=studio_profile,
        )
        storyboard_result, shot_plan = apply_visual_storytelling(
            storyboard_result,
            ROOT,
            style_name="documentary",
        )
        storyboard_result = compile_storyboard_prompts(
            storyboard_result,
            ROOT,
            character_bible=character_result,
            style_name="documentary",
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

        quality_result = inspect_project(
            script=script_result,
            storyboard=storyboard_result,
            character_bible=character_result,
        )
        quality_report_path = folder / "quality-report.json"
        quality_report_path.write_text(
            __import__("json").dumps(quality_result.model_dump(), indent=2),
            encoding="utf-8",
        )

        thumbnail_source = choose_thumbnail_source(folder / "media")
        thumbnail_path = folder / "thumbnail.jpg"
        create_thumbnail(
            source_image=thumbnail_source,
            title=script_result.title,
            output_path=thumbnail_path,
        )

        build_release_package(
            project_dir=folder,
            output=output,
            quality_report=quality_result,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
        )

        write_release_manifest(
            project_dir=folder,
            version="7.0.0",
            project_id=project_id,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            quality_report_path=quality_report_path,
        )

        record_project(
            root=ROOT,
            project_id=project_id,
            topic=request.topic,
            producer_review=producer_result,
            quality_report=quality_result,
            storyboard=storyboard_result,
        )
        save_studio_profile(
            ROOT,
            load_studio_profile(ROOT),
        )

        save_project(output)
        return output
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
