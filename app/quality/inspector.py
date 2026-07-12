from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.narrative.duration_planning import MIN_SCENES

_VALID_MIDDLE_ROLES = {"setup", "conflict", "insight", "resolution"}


@dataclass
class QualityIssue:
    category: str
    severity: str
    message: str


@dataclass
class QualityReport:
    overall_score: int
    hook_score: int
    story_score: int
    continuity_score: int
    cinematography_score: int
    caption_score: int
    audio_score: int
    publish_ready: bool
    issues: list[dict[str, str]]
    recommendations: list[str]

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


def _clamp(value: int) -> int:
    return max(0, min(100, value))


def inspect_project(
    script,
    storyboard,
    character_bible=None,
    requires_character: bool = True,
) -> QualityReport:
    issues: list[QualityIssue] = []
    recommendations: list[str] = []

    hook = (getattr(script, "hook", "") or "").strip()
    hook_score = 92
    if len(hook.split()) < 5:
        hook_score -= 20
        issues.append(QualityIssue("hook", "high", "Hook is too short to establish curiosity."))
    if not any(mark in hook for mark in ("?", "!", "—", ":")):
        hook_score -= 6

    scenes = list(getattr(storyboard, "scenes", []) or [])
    story_score = 95
    roles = [str(getattr(scene, "story_role", "")).lower() for scene in scenes]
    if len(scenes) < MIN_SCENES:
        story_score -= 18
        issues.append(QualityIssue("story", "high", f"Expected at least {MIN_SCENES} scenes, found {len(scenes)}."))
    if roles:
        valid_arc = (
            roles[0] == "hook"
            and roles[-1] == "final_line"
            and all(role in _VALID_MIDDLE_ROLES for role in roles[1:-1])
        )
        if not valid_arc:
            story_score -= 10
            issues.append(QualityIssue("story", "medium", "Scene roles do not follow the intended hook/.../final_line arc."))

    continuity_score = 94
    if character_bible is None and requires_character:
        continuity_score -= 20
        issues.append(QualityIssue("character", "high", "Character Bible is missing."))
    for scene in scenes:
        if not (getattr(scene, "continuity_anchor", "") or "").strip():
            continuity_score -= 4
    if scenes and continuity_score < 85:
        recommendations.append("Add explicit continuity anchors to every scene prompt.")

    cinematography_score = 93
    motions = [str(getattr(scene, "motion_type", "")).lower() for scene in scenes]
    if motions:
        for i in range(2, len(motions)):
            if motions[i] == motions[i - 1] == motions[i - 2]:
                cinematography_score -= 8
                issues.append(QualityIssue("cinematography", "medium", "The same camera motion repeats three times consecutively."))
                break

    caption_score = 94
    for scene in scenes:
        text = (getattr(scene, "on_screen_text", "") or "").strip()
        if len(text.split()) > 9:
            caption_score -= 5
            issues.append(QualityIssue("captions", "medium", f"Scene {getattr(scene, 'number', '?')} caption is too long."))

    audio_score = 92

    weighted = round(
        hook_score * 0.18
        + story_score * 0.22
        + continuity_score * 0.20
        + cinematography_score * 0.16
        + caption_score * 0.12
        + audio_score * 0.12
    )
    overall = _clamp(weighted)
    publish_ready = overall >= 85 and not any(i.severity == "high" for i in issues)

    if not recommendations and publish_ready:
        recommendations.append("No blocking production issues detected.")

    return QualityReport(
        overall_score=overall,
        hook_score=_clamp(hook_score),
        story_score=_clamp(story_score),
        continuity_score=_clamp(continuity_score),
        cinematography_score=_clamp(cinematography_score),
        caption_score=_clamp(caption_score),
        audio_score=_clamp(audio_score),
        publish_ready=publish_ready,
        issues=[asdict(issue) for issue in issues],
        recommendations=recommendations,
    )
