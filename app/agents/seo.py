from __future__ import annotations

from typing import TYPE_CHECKING

from app.model_router.execution import run_agent_stage
from app.model_router.quality_checks import seo_validator
from app.model_router.stages import Stage
from app.models import SeoPackage, ShortScript

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification

INSTRUCTIONS = '''
You are the distribution metadata editor for Mind Frontier Studio.
Create accurate, concise metadata suited to the requested audience, format,
channel, and distribution context.
Do not promise outcomes the video does not deliver.
Use three to five relevant hashtags.
'''


def run(
    script: ShortScript,
    production_specification: ProductionSpecification | None = None,
) -> SeoPackage:
    audience = getattr(production_specification, "audience", None) or "the intended audience"
    output_format = getattr(production_specification, "output_format", None) or "video"
    channel_id = getattr(production_specification, "channel_id", None) or "default channel"
    return run_agent_stage(
        Stage.SEO,
        instructions=INSTRUCTIONS,
        prompt=f'''
Script:
{script.model_dump_json(indent=2)}

Audience: {audience}
Format: {output_format}
Channel: {channel_id}

Create a distribution-ready title, a two-sentence description, and 3-5 hashtags.
''',
        schema=SeoPackage,
        validate=seo_validator(),
    ).output
