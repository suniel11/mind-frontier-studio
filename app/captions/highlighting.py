from __future__ import annotations

"""Keyword highlighting.

At most one span per line is ever highlighted -- "never over-highlight".
The scene's own ``caption_emphasis`` (curated upstream by the storyboard
writer -- it already knows which word or phrase in *this* scene matters
most) is the primary signal. When a line doesn't contain that phrase, a
generic, domain-agnostic fallback looks for the same structural categories
the line-breaking module protects: a name, a date, or a number+unit --
because those are, structurally, what a documentary line most often wants
to land on -- with a last-resort heuristic for unusually long
technical-looking words (a cheap, generic stand-in for "scientific
concept" that doesn't require a topic-specific dictionary).
"""

import re

from app.captions.line_breaking import _DATE_PATTERN, _NAME_PATTERN, _NUMBER_UNIT_PATTERN

_TECHNICAL_WORD = re.compile(r"\b[A-Za-z][A-Za-z-]{9,}\b")


def _find_emphasis_span(line: str, caption_emphasis: str) -> tuple[int, int] | None:
    if not caption_emphasis:
        return None
    match = re.search(re.escape(caption_emphasis), line, flags=re.IGNORECASE)
    return (match.start(), match.end()) if match else None


def _find_structural_span(line: str) -> tuple[int, int] | None:
    for pattern in (_NAME_PATTERN, _DATE_PATTERN, _NUMBER_UNIT_PATTERN, _TECHNICAL_WORD):
        match = pattern.search(line)
        if match:
            return (match.start(), match.end())
    return None


def find_highlight_span(line: str, caption_emphasis: str = "") -> tuple[int, int] | None:
    """Return the (start, end) character span to highlight in ``line``, or
    ``None`` if nothing warrants emphasis."""

    return _find_emphasis_span(line, caption_emphasis) or _find_structural_span(line)
