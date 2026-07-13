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
from app.model_router.project_state import start_project as start_model_routing_project
from app.model_router.usage import save_model_usage
from app.models import ProjectOutput, ProjectRequest
from app.narration.report import build_narration_report, save_narration_report
from app.narration.voice_selection import select_voice
from app.narrative.beats import apply_narrative_beats
from app.narrative.duration_planning import retime_scenes
from app.narrative.report import save_beat_map
from app.operations.telemetry import PipelineTelemetry
from app.producer.review import review_script
from app.producer_ai.reviewer import assess_topic
from app.production.pipeline import compile_storyboard_prompts
from app.production.preference_resolver import resolve_preferences
from app.production.report import save_production_report
from app.production.validation import validate_production
from app.production.voice_timing import synthesize_narration
from app.publishing.assistant import build_publish_package
from app.publishing.manifest import write_release_manifest
from app.publishing.presets import get_channel_preset
from app.publishing.release import build_release_package
from app.publishing.thumbnail import choose_thumbnail_source, create_thumbnail
from app.quality.inspector import inspect_project
from app.services.audio import probe_duration
from app.services.media import build_video, gender_for_voice, generate_voiceover
from app.services.project_store import make_project_id, save_project
from app.visual.pipeline import apply_visual_storytelling
from app.visual_continuity.planner import plan_visual_assets
from app.visual_continuity.telemetry import save_visual_asset_report


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
    # Cost-aware model routing (app.model_router) is scoped to this run via
    # a contextvar so research/script/storyboard/character/seo can resolve
    # their model and report usage without any signature changes.
    start_model_routing_project(project_id)
    # Single source of truth for the whole run: explicit prompt instructions
    # (priority 1) reconciled over whatever the Creative Director's
    # structured specification already set (priority 2). Every downstream
    # stage reads specification.preferences / specification.requires_character
    # instead of inventing its own default. ProjectRequest guarantees
    # production_specification is always populated (see app/models.py).
    specification = resolve_preferences(request.production_specification)
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
                specification.target_seconds,
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
                specification.target_seconds,
                character_result,
                production_specification=specification,
            )

        with tracked_stage("narrative_beats"):
            storyboard_result, narrative_beats = apply_narrative_beats(
                storyboard_result,
                specification.target_seconds,
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

        with tracked_stage("visual_continuity"):
            # Visual Asset Economy v3: decide which adjacent scenes are the
            # same visual moment and can share one generated image (each
            # presented with a different camera treatment). Runs after
            # prompt_compilation so it sees every scene's final, compiled
            # image_prompt. Safe by construction -- disabled, a provider
            # failure, or a structurally unusable plan all degrade to
            # today's one-image-per-scene behavior (see
            # app.visual_continuity.planner._identity_plan).
            visual_asset_plan = plan_visual_assets(
                storyboard_result,
                target_seconds=specification.target_seconds,
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
            # Text-model usage (Phase 10) for every stage up to this point
            # (research/script/character/storyboard/seo). Re-saved at
            # final_save too in case a later stage (e.g. a runtime script
            # resize during voice_generation) adds more calls.
            save_model_usage(project_dir, project_id)
            save_cinema_report(project_dir, cinema_report)
            save_visual_asset_report(project_dir, visual_asset_plan, storyboard_result)

        with tracked_stage("voice_generation"):
            # Narration is synthesized here (not inside the renderer) so its
            # *measured* duration -- not the originally requested duration --
            # can drive scene timing. If the script came out the wrong
            # length, it is corrected and re-synthesized (bounded retries)
            # before any scene timing is finalized.
            media_dir = project_dir / "media"
            media_dir.mkdir(exist_ok=True)
            # Distinct from the "voiceover.mp3" build_video writes to when it
            # copies this file in -- same path would make that copy a no-op
            # source==dest error.
            narration_audio_path = media_dir / "narration-source.mp3"
            voice_selection = select_voice(character_result, specification.preferences)
            narrator_voice = voice_selection.voice
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()

            script_result, narration_seconds = synthesize_narration(
                script_result,
                specification.target_seconds,
                narration_audio_path,
                synthesize=lambda s, path: generate_voiceover(
                    s, path, voice=narrator_voice, preferences=specification.preferences,
                    cancellation_check=cancellation_check,
                ),
                probe_duration=lambda path: probe_duration(ffmpeg_exe, path),
                resize_script=script.resize,
            )
            retime_scenes(storyboard_result, narration_seconds)

            narration_report = build_narration_report(
                specification.preferences, voice_selection, provider="openai"
            )
            save_narration_report(project_dir, narration_report)
            output.warnings.extend(narration_report.warnings)

            output.script = script_result
            output.storyboard = storyboard_result
            save_project(output)

        with tracked_stage("render"):
            video_path = build_video(
                project_dir,
                script_result,
                storyboard_result,
                narration_audio_path=narration_audio_path,
                preferences=specification.preferences,
                aspect_ratio=specification.aspect_ratio,
                cancellation_check=cancellation_check,
            )
            output.video_url = f"/projects/{project_id}/{video_path.name}"

        with tracked_stage("quality_inspection"):
            quality_result = inspect_project(
                script=script_result,
                storyboard=storyboard_result,
                character_bible=character_result,
                requires_character=requires_character_bible(specification),
            )

            # Requested-vs-actual validation: never silently replaces a
            # preference, only records whether the final production actually
            # matched what was asked for.
            validation_report = validate_production(
                specification,
                actual_duration_seconds=narration_seconds,
                narrator_voice=narrator_voice,
                narrator_gender_actual=gender_for_voice(narrator_voice),
                character_bible=character_result,
                aspect_ratio_actual=specification.aspect_ratio,
            )
            save_production_report(project_dir, validation_report)
            # Surface mismatches on the output itself -- never silently
            # substituted, always visible to whoever reads the project.
            output.warnings.extend(validation_report.warnings)

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
            save_model_usage(project_dir, project_id)

        success = True
        return output
    finally:
        telemetry.finish(project_dir, success)
