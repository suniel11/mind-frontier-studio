from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Callable, Iterator

import imageio_ffmpeg

from app.agents import character, research, script, storyboard, seo
from app.cinema.director import apply_cinematic_direction
from app.cinema.report import save_cinema_report
from app.core.settings import settings
from app.director.engine import apply_director_engine
from app.learning.memory import record_project
from app.learning.profile import load_studio_profile, save_studio_profile
from app.models import ProjectOutput, ProjectRequest
from app.narrative.beats import apply_narrative_beats
from app.narrative.duration_planning import retime_scenes
from app.narrative.report import save_beat_map
from app.operations.telemetry import PipelineTelemetry
from app.producer.review import review_script
from app.producer_ai.reviewer import assess_topic
from app.production.pipeline import compile_storyboard_prompts
from app.production.voice_timing import synthesize_narration
from app.publishing.assistant import build_publish_package
from app.publishing.manifest import write_release_manifest
from app.publishing.presets import get_channel_preset
from app.publishing.release import build_release_package
from app.publishing.thumbnail import choose_thumbnail_source, create_thumbnail
from app.quality.inspector import inspect_project
from app.services.audio import probe_duration
from app.services.media import build_video, generate_voiceover, voice_for_character
from app.services.project_store import make_project_id, save_project
from app.visual.pipeline import apply_visual_storytelling


class PipelineCancelledError(RuntimeError):
    """Raised when a persistent production job asks the pipeline to stop."""


def requires_character_bible(specification) -> bool:
    """Whether this production should get a Character Bible at all.

    Unknown/legacy specifications (``None``) preserve prior behavior.
    Shared by the character-generation stage and the quality inspector so
    the two can never disagree about whether a presenter identity was
    supposed to exist.
    """

    return specification is None or specification.requires_character


def create_project_pipeline(
    request: ProjectRequest,
    *,
    project_id: str | None = None,
    progress_callback: Callable[[str, str], None] | None = None,
    cancellation_check: Callable[[], bool] | None = None,
) -> ProjectOutput:
    project_id = project_id or make_project_id(request.topic)
    specification = request.production_specification
    telemetry = PipelineTelemetry(settings.root, project_id)
    project_dir = None
    success = False

    def check_cancelled() -> None:
        if cancellation_check and cancellation_check():
            raise PipelineCancelledError("Production job was cancelled.")

    @contextmanager
    def tracked_stage(stage: str) -> Iterator[None]:
        check_cancelled()
        if progress_callback:
            progress_callback(stage, "started")
        try:
            with telemetry.stage(stage):
                yield
        except Exception:
            if progress_callback:
                progress_callback(stage, "failed")
            raise
        check_cancelled()
        if progress_callback:
            progress_callback(stage, "complete")

    try:
        with tracked_stage("producer_preflight"):
            preflight = assess_topic(settings.root, request.topic)
            if preflight.overall_score < 35:
                raise RuntimeError(
                    "AI Producer rejected this topic before production: "
                    f"{preflight.verdict}. "
                    f"Suggested angle: {preflight.suggested_angle}"
                )

        with tracked_stage("research"):
            research_result = research.run(
                request.topic,
                production_specification=specification,
            )

        with tracked_stage("script"):
            script_result = script.run(
                request.topic,
                research_result,
                request.target_seconds,
                production_specification=specification,
            )

        with tracked_stage("producer_review"):
            producer_result = review_script(script_result)
            if not producer_result.approved:
                raise RuntimeError(
                    "Producer review rejected the script: "
                    + " ".join(producer_result.notes)
                )

        with tracked_stage("character"):
            # A Character Bible is only generated when the production
            # actually needs a recurring presenter -- when
            # requires_character is False, no identity exists for any
            # subsystem to inject into image prompts or narrator voice
            # selection. Unknown/legacy specifications keep prior behavior.
            character_result = (
                character.run(script_result, production_specification=specification)
                if requires_character_bible(specification)
                else None
            )

        with tracked_stage("storyboard"):
            storyboard_result = storyboard.run(
                script_result,
                request.target_seconds,
                character_result,
                production_specification=specification,
            )

        with tracked_stage("narrative_beats"):
            storyboard_result, narrative_beats = apply_narrative_beats(
                storyboard_result,
                request.target_seconds,
            )

        with tracked_stage("director"):
            studio_profile = load_studio_profile(settings.root)
            storyboard_result, _director_plan = apply_director_engine(
                storyboard_result,
                studio_profile=studio_profile,
                production_specification=specification,
            )

        with tracked_stage("visual_storytelling"):
            storyboard_result, _shot_plan = apply_visual_storytelling(
                storyboard_result,
                settings.root,
                style_name="documentary",
                production_specification=specification,
            )

        with tracked_stage("cinema_direction"):
            storyboard_result, cinema_report = apply_cinematic_direction(
                storyboard_result,
            )

        with tracked_stage("prompt_compilation"):
            storyboard_result = compile_storyboard_prompts(
                storyboard_result,
                settings.root,
                character_bible=character_result,
                style_name="documentary",
            )

        with tracked_stage("seo"):
            seo_result = seo.run(
                script_result,
                production_specification=specification,
            )

        output = ProjectOutput(
            project_id=project_id,
            topic=request.topic,
            research=research_result,
            script=script_result,
            storyboard=storyboard_result,
            character_bible=character_result,
            seo=seo_result,
            production_specification=specification,
        )

        with tracked_stage("project_storage"):
            project_dir = save_project(output)
            save_beat_map(project_dir, narrative_beats)
            save_cinema_report(project_dir, cinema_report)

        with tracked_stage("voice_generation"):
            # Narration is synthesized here (not inside the renderer) so its
            # *measured* duration -- not the originally requested duration --
            # can drive scene timing. If the script came out the wrong
            # length, it is corrected and re-synthesized (bounded retries)
            # before any scene timing is finalized.
            media_dir = project_dir / "media"
            media_dir.mkdir(exist_ok=True)
            narration_audio_path = media_dir / "voiceover.mp3"
            narrator_voice = voice_for_character(character_result)
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

            script_result, narration_seconds = synthesize_narration(
                script_result,
                request.target_seconds,
                narration_audio_path,
                synthesize=lambda s, path: generate_voiceover(s, path, voice=narrator_voice),
                probe_duration=lambda path: probe_duration(ffmpeg_exe, path),
                resize_script=script.resize,
            )
            retime_scenes(storyboard_result, narration_seconds)

            output.script = script_result
            output.storyboard = storyboard_result
            save_project(output)

        with tracked_stage("render"):
            video_path = build_video(
                project_dir,
                script_result,
                storyboard_result,
                narration_audio_path=narration_audio_path,
            )
            output.video_url = f"/projects/{project_id}/{video_path.name}"

        with tracked_stage("quality_inspection"):
            quality_result = inspect_project(
                script=script_result,
                storyboard=storyboard_result,
                character_bible=character_result,
                requires_character=requires_character_bible(specification),
            )
            quality_report_path = project_dir / "quality-report.json"
            quality_report_path.write_text(
                json.dumps(quality_result.model_dump(), indent=2),
                encoding="utf-8",
            )

        with tracked_stage("thumbnail"):
            thumbnail_source = choose_thumbnail_source(project_dir / "media")
            thumbnail_path = project_dir / "thumbnail.jpg"
            create_thumbnail(
                source_image=thumbnail_source,
                title=script_result.title,
                output_path=thumbnail_path,
            )

        with tracked_stage("release_package"):
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
            build_publish_package(
                project_dir=project_dir,
                channel=get_channel_preset(settings.root, "mind-frontier"),
            )

        with tracked_stage("studio_memory"):
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

        with tracked_stage("final_save"):
            save_project(output)

        success = True
        return output
    finally:
        telemetry.finish(project_dir, success)
