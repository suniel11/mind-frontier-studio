from app.models import ResearchBrief, ShortScript
from app.services.openai_client import structured_response

INSTRUCTIONS = '''
You are the Script Agent for Mind Frontier.
Write calm, cinematic, intellectually engaging narration.
Avoid generic motivational filler, fake certainty, clickbait shouting, and "follow for more."
The first sentence must create immediate curiosity.
Use one memorable idea and end with a strong insight.
Write original wording.
'''

def run(topic: str, research: ResearchBrief, target_seconds: int) -> ShortScript:
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f'''
Topic: {topic}
Target duration: {target_seconds} seconds

Research brief:
{research.model_dump_json(indent=2)}

Write a complete voiceover of approximately {target_seconds * 2.2:.0f} words.
The title should be compelling but accurate.
The hook must work in the first two seconds.
The ending should feel conclusive, not promotional.
''',
        schema=ShortScript,
    )
