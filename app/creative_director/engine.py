from typing import List

from .models import DirectorQuestion


class CreativeDirector:

    def generate_questions(self, prompt: str) -> List[DirectorQuestion]:

        prompt_lower = prompt.lower()

        questions = []

        # audience

        questions.append(
            DirectorQuestion(
                id="audience",
                question="Who is the intended audience?",
                options=[
                    "General audience",
                    "Students",
                    "Professionals",
                    "Children"
                ]
            )
        )

        # runtime

        questions.append(
            DirectorQuestion(
                id="runtime",
                question="How long should this video be?",
                options=[
                    "30",
                    "45",
                    "60",
                    "90"
                ]
            )
        )

        if "history" in prompt_lower \
        or "napoleon" in prompt_lower \
        or "roman" in prompt_lower:

            questions.append(
                DirectorQuestion(
                    id="accuracy",
                    question="How historically accurate should it be?",
                    options=[
                        "Strict",
                        "Balanced",
                        "Creative"
                    ]
                )
            )

        if "science" in prompt_lower \
        or "physics" in prompt_lower \
        or "quantum" in prompt_lower:

            questions.append(
                DirectorQuestion(
                    id="complexity",
                    question="Technical depth?",
                    options=[
                        "Simple",
                        "Medium",
                        "Advanced"
                    ]
                )
            )

        if "story" in prompt_lower \
        or "fiction" in prompt_lower:

            questions.append(
                DirectorQuestion(
                    id="ending",
                    question="Preferred ending?",
                    options=[
                        "Twist",
                        "Open",
                        "Happy",
                        "Dark"
                    ]
                )
            )

        questions.append(
            DirectorQuestion(
                id="tone",
                question="Overall tone?",
                options=[
                    "Cinematic",
                    "Educational",
                    "Inspirational",
                    "Dark",
                    "Emotional"
                ]
            )
        )

        return questions

    def build_brief(
        self,
        prompt,
        answers
    ):

        runtime = int(
            answers.get(
                "runtime",
                45
            )
        )

        hook = "direct contradiction"

        brief = f"""
User Idea

{prompt}

Production Notes

{answers}

Requirements

Strong hook

Clear escalation

Professional pacing

Visual storytelling

Strong ending

"""

        return {

            "topic": prompt,

            "target_seconds": runtime,

            "hook_type": hook,

            "creative_brief": brief

        }


director = CreativeDirector()