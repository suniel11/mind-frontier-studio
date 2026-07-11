from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass
class ProducerReview:
    approved: bool
    score: int
    notes: list[str]

    def model_dump(self):
        return asdict(self)


def review_script(script) -> ProducerReview:
    notes: list[str] = []
    score = 100

    hook = (getattr(script, "hook", "") or "").strip()
    voiceover = (getattr(script, "voiceover", "") or "").strip()
    ending = (getattr(script, "ending", "") or "").strip()

    if len(hook.split()) < 6:
        score -= 18
        notes.append("Strengthen the opening hook before rendering.")
    if len(voiceover.split()) < 70:
        score -= 12
        notes.append("The narration may be too thin for a complete short.")
    if len(voiceover.split()) > 180:
        score -= 10
        notes.append("The narration may feel rushed at short-form pacing.")
    if len(ending.split()) < 4:
        score -= 10
        notes.append("The ending needs a clearer final thought.")
    if not notes:
        notes.append("Script passed producer review.")

    return ProducerReview(
        approved=score >= 75,
        score=max(0, min(100, score)),
        notes=notes,
    )
