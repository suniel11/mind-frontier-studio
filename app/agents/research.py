from __future__ import annotations

import json
from typing import TYPE_CHECKING

from app.models import ResearchBrief
from app.services.openai_client import structured_response

if TYPE_CHECKING:
    from app.production.specification import ProductionSpecification

INSTRUCTIONS = '''
You are the Research Agent for Mind Frontier Studio.
Produce careful, production-useful research for any creative video format.
Do not invent studies, statistics, quotations, or authorities.
Prefer stable, widely supported explanations.
Mark uncertainty in cautions.
Keep each point concise and usable by a scriptwriter.
Respect the requested accuracy level, audience, objective, and creative format.
For fictional work, clearly separate factual context from invented story material.
'''


def _specification_context(
    production_specification: ProductionSpecification | None,
) -> str:
    if production_specification is None:
        return ""
    payload = {
        key: value
        for key, value in production_specification.model_dump().items()
        if value not in (None, "", [])
    }
    return "\nProduction specification:\n" + json.dumps(
        payload,
        ensure_ascii=False,
        indent=2,
    )


def run(
    topic: str,
    production_specification: ProductionSpecification | None = None,
) -> ResearchBrief:
    target_seconds = getattr(production_specification, "target_seconds", 45)
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f'''
Topic: {topic}

Develop a research brief for a production of approximately {target_seconds} seconds.
Focus on the central idea rather than listing disconnected facts.
Return a strong audience-relevant framing and useful possible angles.
{_specification_context(production_specification)}
''',
        schema=ResearchBrief,
    )
