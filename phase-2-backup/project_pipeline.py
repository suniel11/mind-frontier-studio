from __future__ import annotations

import json

from app.agents import character, research, script, storyboard, seo
from app.core.settings import settings
from app.director.engine import apply_director_engine
from app.learning.memory import record_project
from app.learning.profile import load_studio_profile, save_studio_profile
from app.models import ProjectOutput, ProjectRequest
from app.narrative.beats import apply_narrative_beats
from app.narrative.report import save_beat_map
from app.producer.review import review_script
from app.production.pipeline import compile_storyboard_prompts
from app.publishing.manifest import write_release_manifest
from app.publishing.release import build_release_package
from app.publishing.thumbnail import choose_thumbnail_source, create_thumbnail
from app.quality.inspector import inspect_project
from app.services.media import build_video
from app.services.project_store import make_project_id, save_project
from app.visual.pipeline import apply_visual_storytelling


def create_project_pipeline(request: ProjectRequest) -> ProjectOutput:
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

    storyboard_result, narrative_beats = apply_narrative_beats(
        storyboard_result,
        request.target_seconds,
    )

    studio_profile = load_studio_profile(settings.root)
    storyboard_result, _director_plan = apply_director_engine(
        storyboard_result,
        studio_profile=studio_profile,
    )

    storyboard_result, _shot_plan = apply_visual_storytelling(
        storyboard_result,
        settings.root,
        style_name="documentary",
    )

    storyboard_result = compile_storyboard_prompts(
        storyboard_result,
        settings.root,
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

    project_dir = save_project(output)
    save_beat_map(project_dir, narrative_beats)

    video_path = build_video(
        project_dir,
        script_result,
        storyboard_result,
    )
    output.video_url = f"/projects/{project_id}/{video_path.name}"

    quality_result = inspect_project(
        script=script_result,
        storyboard=storyboard_result,
        character_bible=character_result,
    )

    quality_report_path = project_dir / "quality-report.json"
    quality_report_path.write_text(
        json.dumps(quality_result.model_dump(), indent=2),
        encoding="utf-8",
    )

    thumbnail_source = choose_thumbnail_source(project_dir / "media")
    thumbnail_path = project_dir / "thumbnail.jpg"
    create_thumbnail(
        source_image=thumbnail_source,
        title=script_result.title,
        output_path=thumbnail_path,
    )

    build_release_package(
        project_dir=project_dir,
        output=output,
        quality_report=quality_result,
        video_path=video_path,
        thumbnail_path=thumbnail_path,
    )

    write_release_manifest(
        project_dir=project_dir,
        version=settings.version,
        project_id=project_id,
        video_path=video_path,
        thumbnail_path=thumbnail_path,
        quality_report_path=quality_report_path,
    )

    record_project(
        root=settings.root,
        project_id=project_id,
        topic=request.topic,
        producer_review=producer_result,
        quality_report=quality_result,
        storyboard=storyboard_result,
    )

    save_studio_profile(
        settings.root,
        load_studio_profile(settings.root),
    )

    save_project(output)
    return output
