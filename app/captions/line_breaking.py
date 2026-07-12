from __future__ import annotations

"""Natural-language caption segmentation.

Breaks narration into caption *cards* (1-2 lines shown together) without
ever wrapping mid-word or mid-unit. Preference order for where a line/card
boundary may fall: sentence end > clause end (;:) > phrase end (,) > a
plain word boundary once the hard word cap is reached. Names, numbers with
units, and dates are detected up front and treated as single unbreakable
chunks so a line break can never land inside "Marie Curie" or "3.7 billion".

Deterministic, pure-Python, no model calls -- caption rendering must stay
reproducible.
"""

import re
from dataclasses import dataclass

MAX_LINES_PER_CARD = 2
TARGET_MIN_WORDS_PER_LINE = 3
TARGET_MAX_WORDS_PER_LINE = 6
HARD_MAX_WORDS_PER_LINE = 8
# A word-count cap alone isn't enough to guarantee a line fits the frame --
# eight long words ("extraordinarily", "terminology", ...) can be far wider
# than eight short ones. This is sized so font_scaling.py can always find a
# size at or above its readability floor that fits within the narrowest
# supported aspect ratio's safe width -- see app/captions/font_scaling.py.
HARD_MAX_CHARS_PER_LINE = 38

_SENTENCE_END = re.compile(r"[.!?]$")
_CLAUSE_END = re.compile(r"[;:]$")
_PHRASE_END = re.compile(r",$")

_MONTHS = (
    "January", "February", "March", "April", "May", "June", "July",
    "August", "September", "October", "November", "December",
)
_MONTH_GROUP = "|".join(_MONTHS)

# Protected spans: never split a line/word boundary inside these.
_DATE_PATTERN = re.compile(
    rf"\b(?:{_MONTH_GROUP})\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,\s*\d{{3,4}})?\b"
    rf"|\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTH_GROUP})\b"
)
_NUMBER_UNIT_PATTERN = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*(?:percent|%|million|billion|trillion|thousand|hundred|"
    r"years?|kilometers?|km|miles?|meters?|degrees?|light-years?)\b",
    re.IGNORECASE,
)
# A run of two-plus capitalized words -- a proper-noun sequence (person,
# place, institution name) that should stay on one line together.
_NAME_PATTERN = re.compile(r"\b[A-Z][a-zA-Z'.-]*(?:\s+[A-Z][a-zA-Z'.-]*){1,3}\b")


@dataclass
class CaptionCard:
    lines: list[str]
    word_count: int

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _find_protected_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    for pattern in (_DATE_PATTERN, _NUMBER_UNIT_PATTERN, _NAME_PATTERN):
        spans.extend((m.start(), m.end()) for m in pattern.finditer(text))
    spans.sort()

    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _chunk_text(text: str) -> list[str]:
    """Split into atomic chunks: single words, except protected spans (a
    name, a date, a number+unit) which become one multi-word chunk."""

    protected = _find_protected_spans(text)
    words = list(re.finditer(r"\S+", text))
    chunks: list[str] = []
    index = 0
    while index < len(words):
        word = words[index]
        span = next((p for p in protected if p[0] <= word.start() < p[1]), None)
        if span is None:
            chunks.append(word.group())
            index += 1
            continue
        group = []
        while index < len(words) and words[index].start() < span[1]:
            group.append(words[index].group())
            index += 1
        chunks.append(" ".join(group))
    return chunks


def segment_into_caption_cards(text: str) -> list[CaptionCard]:
    """Turn narration text into a sequence of 1-2-line caption cards.

    A sentence that runs long produces additional cards rather than
    overflowing a card past two lines -- this is what keeps up with fast
    narration without ever clipping or cramming text.
    """

    normalized = re.sub(r"\s+", " ", text.strip())
    if not normalized:
        return []

    chunks = _chunk_text(normalized)
    cards: list[CaptionCard] = []
    lines: list[list[str]] = [[]]

    def line_word_count(line: list[str]) -> int:
        return sum(len(chunk.split()) for chunk in line)

    def line_char_count(line: list[str]) -> int:
        return len(" ".join(line))

    def flush_card() -> None:
        nonlocal lines
        rendered = [" ".join(line) for line in lines if line]
        if rendered:
            cards.append(CaptionCard(lines=rendered, word_count=sum(len(l.split()) for l in rendered)))
        lines = [[]]

    for chunk in chunks:
        chunk_words = len(chunk.split())
        current_line = lines[-1]
        projected_words = line_word_count(current_line) + chunk_words
        projected_chars = line_char_count(current_line) + (1 if current_line else 0) + len(chunk)

        must_break_line = current_line and (
            projected_words > HARD_MAX_WORDS_PER_LINE
            or projected_chars > HARD_MAX_CHARS_PER_LINE
            or line_word_count(current_line) >= TARGET_MAX_WORDS_PER_LINE
        )
        if must_break_line:
            if len(lines) >= MAX_LINES_PER_CARD:
                flush_card()
            else:
                lines.append([])
            current_line = lines[-1]

        current_line.append(chunk)

        if line_word_count(current_line) >= TARGET_MIN_WORDS_PER_LINE:
            if _SENTENCE_END.search(chunk):
                flush_card()
            elif _CLAUSE_END.search(chunk) or _PHRASE_END.search(chunk):
                if len(lines) < MAX_LINES_PER_CARD:
                    lines.append([])
                # already at the line cap: keep filling until forced to break

    flush_card()
    return cards
