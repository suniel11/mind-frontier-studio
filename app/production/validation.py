from __future__ import annotations

"""Requested-vs-actual validation, run right before a project is considered
finished. Per-field checks never mutate anything -- a mismatch becomes a
warning attached to the project, not a silent substitution. This is what
lets a creator (or a future automated check) see exactly which explicit
instructions the pipeline actually honored.
"""

from dataclasses import asdict, dataclass
from typing import Any

from app.narrative.duration_planning import duration_within_tolerance


@dataclass
class PreferenceCheck:
    label: str
    requested: str
    actual: str
    passed: bool

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    checks: list[PreferenceCheck]
    warnings: list[str]

    @property
    def all_passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def model_dump(self) -> dict[str, Any]:
        return {
            "checks": [check.model_dump() for check in self.checks],
            "warnings": list(self.warnings),
            "all_passed": self.all_passed,
        }


def validate_production(
    specification,
    *,
    actual_duration_seconds: float,
    narrator_voice: str,
    narrator_gender_actual: str | None,
    character_bible,
    aspect_ratio_actual: str,
) -> ValidationReport:
    checks: list[PreferenceCheck] = []
    warnings: list[str] = []
    preferences = specification.preferences

    requested_seconds = specification.target_seconds
    duration_ok = duration_within_tolerance(actual_duration_seconds, requested_seconds)
    checks.append(
        PreferenceCheck(
            "Runtime", f"{requested_seconds}s", f"{round(actual_duration_seconds)}s", duration_ok
        )
    )
    if not duration_ok:
        warnings.append(
            f"Runtime differs from the request: asked for {requested_seconds}s, "
            f"produced {round(actual_duration_seconds)}s."
        )

    requested_gender = preferences.narrator.gender
    if requested_gender is not None:
        gender_ok = narrator_gender_actual == requested_gender
        checks.append(
            PreferenceCheck(
                "Narrator gender",
                requested_gender,
                narrator_gender_actual or "unspecified",
                gender_ok,
            )
        )
        if not gender_ok:
            warnings.append(
                f"Requested a {requested_gender} narrator but the selected voice "
                f"({narrator_voice}) resolved to {narrator_gender_actual or 'unspecified'}."
            )

    requested_presenter = specification.requires_character
    actual_presenter = character_bible is not None
    presenter_ok = requested_presenter == actual_presenter
    checks.append(
        PreferenceCheck(
            "Presenter enabled",
            "yes" if requested_presenter else "no",
            "yes" if actual_presenter else "no",
            presenter_ok,
        )
    )
    if not presenter_ok:
        warnings.append("Presenter enabled/disabled state does not match the request.")

    requested_presenter_gender = preferences.presenter.gender
    if requested_presenter_gender is not None and character_bible is not None:
        actual_presenter_gender = str(getattr(character_bible, "gender", "") or "").strip().casefold() or None
        gender_ok = actual_presenter_gender == requested_presenter_gender
        checks.append(
            PreferenceCheck(
                "Presenter gender",
                requested_presenter_gender,
                actual_presenter_gender or "unspecified",
                gender_ok,
            )
        )
        if not gender_ok:
            warnings.append(
                f"Requested a {requested_presenter_gender} presenter but the Character "
                f"Bible resolved to {actual_presenter_gender or 'unspecified'}."
            )

    requested_ratio = specification.aspect_ratio
    ratio_ok = requested_ratio == aspect_ratio_actual
    checks.append(PreferenceCheck("Aspect ratio", requested_ratio, aspect_ratio_actual, ratio_ok))
    if not ratio_ok:
        warnings.append(
            f"Aspect ratio differs: requested {requested_ratio}, rendered {aspect_ratio_actual}."
        )

    if preferences.narrator.language:
        warnings.append(
            f"Language preference '{preferences.narrator.language}' was captured but is not "
            "yet enforced -- narration language follows the script text, not a selectable parameter."
        )
    if preferences.narrator.accent:
        warnings.append(
            f"Accent preference '{preferences.narrator.accent}' was captured but is not yet "
            "enforced by the narration pipeline."
        )
    if preferences.rendering.transitions:
        warnings.append(
            f"Transition style preference '{preferences.rendering.transitions}' was captured "
            "but is not yet enforced by the renderer (no cross-fade transitions are implemented)."
        )

    return ValidationReport(checks=checks, warnings=warnings)
