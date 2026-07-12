from __future__ import annotations

"""Merges creator preferences from every priority tier into one resolved
ProductionSpecification -- the single source of truth every downstream stage
should read.

Priority order (highest wins, field by field):
1. Explicit user prompt (deterministic extraction; see
   app/production/preference_extraction.py -- not an LLM's best-effort
   paraphrase of the prompt, so it cannot be softened or dropped in transit).
2. Production specification (the Creative Director's structured output).
3. Character Bible -- not merged here; it is generated *after* this
   resolution runs, so higher-priority narrator/presenter fields become hard
   constraints the Character Bible must honor instead (see
   app/agents/character.py and app/services/media.py's voice_for_character).
4. Genre defaults -- applied downstream where a genre-specific mechanism
   already exists and no higher-priority value was set (e.g. presenter
   frequency caps in app/visual/genre.py).
5. System defaults -- whatever a field's own model default already is.
"""

from app.production.preference_extraction import extract_explicit_preferences
from app.production.specification import ProductionSpecification


def resolve_preferences(specification: ProductionSpecification) -> ProductionSpecification:
    """Return a copy of ``specification`` with ``.preferences`` fully
    resolved and ``.aspect_ratio``/``.target_seconds`` reconciled against any
    explicit prompt instruction.

    Idempotent: re-running it on an already-resolved specification is a
    no-op, since re-extracting the same original_prompt yields the same
    explicit layer, which still wins the same way.
    """

    explicit = extract_explicit_preferences(specification.original_prompt)
    resolved = explicit.merged_over(specification.preferences)

    updates: dict[str, object] = {"preferences": resolved}
    if resolved.video.aspect_ratio is not None:
        updates["aspect_ratio"] = resolved.video.aspect_ratio
    if resolved.video.runtime_seconds is not None:
        updates["target_seconds"] = resolved.video.runtime_seconds

    return specification.model_copy(update=updates)
