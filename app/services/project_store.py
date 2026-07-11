import json
import re
import time
from pathlib import Path
from app.models import ProjectOutput

ROOT = Path(__file__).resolve().parents[2]
PROJECTS = ROOT / "projects"
PROJECTS.mkdir(exist_ok=True)

def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value[:60] or "untitled"

def project_folder(project_id: str) -> Path:
    return PROJECTS / project_id

def save_project(project: ProjectOutput) -> Path:
    folder = project_folder(project.project_id)
    folder.mkdir(parents=True, exist_ok=True)

    payloads = {
        "project.json": project.model_dump(),
        "research.json": project.research.model_dump(),
        "script.json": project.script.model_dump(),
        "storyboard.json": project.storyboard.model_dump(),
        "seo.json": project.seo.model_dump(),
    }

    for name, payload in payloads.items():
        (folder / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    (folder / "voiceover.txt").write_text(project.script.voiceover, encoding="utf-8")
    return folder

def make_project_id(topic: str) -> str:
    return f"{int(time.time())}-{slugify(topic)}"
