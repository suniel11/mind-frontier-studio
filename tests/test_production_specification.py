from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import ProjectRequest
from app.production.specification import ProductionSpecification


def test_legacy_project_request_creates_canonical_specification():
    request = ProjectRequest(topic="Explain how a heat pump works", target_seconds=75)

    assert request.topic == "Explain how a heat pump works"
    assert request.target_seconds == 75
    assert request.production_specification is not None
    assert request.production_specification.original_prompt == request.topic
    assert request.production_specification.aspect_ratio == "9:16"


def test_structured_project_request_needs_no_flattened_topic():
    specification = ProductionSpecification(
        original_prompt="Launch a handmade ceramic collection",
        target_seconds=120,
        aspect_ratio="landscape",
        visual_style="Textured stop motion",
        tone="Playful",
    )

    request = ProjectRequest(production_specification=specification)

    assert request.topic == specification.original_prompt
    assert request.target_seconds == 120
    assert request.production_specification.aspect_ratio == "16:9"


@pytest.mark.parametrize("seconds", [19, 181])
def test_specification_rejects_runtime_outside_supported_range(seconds):
    with pytest.raises(ValidationError):
        ProductionSpecification(original_prompt="A valid creative prompt", target_seconds=seconds)


def test_specification_rejects_unsupported_aspect_ratio():
    with pytest.raises(ValidationError):
        ProductionSpecification(
            original_prompt="A valid creative prompt",
            aspect_ratio="21:9",
        )
