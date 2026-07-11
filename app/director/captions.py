from __future__ import annotations

import re


def semantic_phrases(text: str, max_words: int = 5) -> list[str]:
    text = re.sub(r"\s+", " ", text.strip())
    if not text:
        return []

    sentence_parts = re.split(r"(?<=[.!?;:])\s+", text)
    phrases: list[str] = []

    for sentence in sentence_parts:
        words = sentence.split()
        if not words:
            continue

        current: list[str] = []
        for word in words:
            current.append(word)
            natural_break = word.endswith((",", ";", ":", ".", "!", "?"))
            if len(current) >= max_words or (natural_break and len(current) >= 2):
                phrases.append(" ".join(current))
                current = []

        if current:
            if phrases and len(current) <= 2:
                phrases[-1] = f"{phrases[-1]} {' '.join(current)}"
            else:
                phrases.append(" ".join(current))

    return phrases
