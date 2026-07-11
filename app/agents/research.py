from app.models import ResearchBrief
from app.services.openai_client import structured_response

INSTRUCTIONS = '''
You are the Research Agent for Mind Frontier, a faceless documentary brand.
Produce careful, useful research for a short-form video.
Do not invent studies, statistics, quotations, or authorities.
Prefer stable, widely supported explanations.
Mark uncertainty in cautions.
Keep each point concise and usable by a scriptwriter.
'''

def run(topic: str) -> ResearchBrief:
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f'''
Topic: {topic}

Develop a research brief for a 20-60 second YouTube Short.
The Short must explain one central idea rather than list many facts.
Return a strong audience-relevant framing and three possible angles.
''',
        schema=ResearchBrief,
    )
