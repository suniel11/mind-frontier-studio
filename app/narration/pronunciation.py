from __future__ import annotations

"""Pronunciation hints for TTS input text.

Whole-word, case-insensitive respelling applied only to the copy of text
sent to voice synthesis -- ``scene.narration`` (what captions read) is never
touched, so what's on screen always matches what was written even when the
spoken form is respelled for clarity.

The bundled dictionary is intentionally small: it demonstrates the
substitution mechanism honestly rather than pretending to comprehensively
cover every scientific/historical name a documentary might use. Real
broad-coverage pronunciation correction needs a grapheme-to-phoneme model or
a much larger curated dataset -- out of scope for this pass (see the
project report's limitations). Callers may supply their own ``hints`` table
to extend or override entries.
"""

import re

# A representative starter set spanning the categories the task calls out:
# scientific names, historical names, locations, technical terminology.
PRONUNCIATION_HINTS: dict[str, str] = {
    "nietzsche": "NEE-cha",
    "einstein": "EYEN-stine",
    "sisyphus": "SIS-if-us",
    "dvorak": "vor-ZHAHK",
    "worcester": "WUS-ter",
    "arkansas": "AR-kan-saw",
    "nguyen": "win",
    "xi'an": "shee-AHN",
    "reykjavik": "RAKE-yah-vik",
    "quinoa": "KEEN-wah",
    "genghis": "JENG-gis",
    "euler": "OY-ler",
    "goethe": "GUR-tuh",
    "hermione": "her-MY-oh-nee",
    "epstein": "EP-stine",
}

_WORD_PATTERN = re.compile(r"[A-Za-z']+")


def apply_pronunciation_hints(text: str, hints: dict[str, str] | None = None) -> str:
    """Return a TTS-input copy of ``text`` with known tricky terms respelled
    phonetically. Never modifies caption source text."""

    table = hints if hints is not None else PRONUNCIATION_HINTS
    if not table:
        return text

    def replace(match: re.Match) -> str:
        word = match.group(0)
        hint = table.get(word.casefold())
        return hint if hint else word

    return _WORD_PATTERN.sub(replace, text)
