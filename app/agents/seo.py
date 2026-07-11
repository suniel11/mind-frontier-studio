from app.models import ShortScript, SeoPackage
from app.services.openai_client import structured_response

INSTRUCTIONS = '''
You are the YouTube metadata editor for Mind Frontier.
Create accurate, concise metadata.
Do not promise outcomes the video does not deliver.
Use three to five relevant hashtags.
'''

def run(script: ShortScript) -> SeoPackage:
    return structured_response(
        instructions=INSTRUCTIONS,
        prompt=f'''
Script:
{script.model_dump_json(indent=2)}

Create a YouTube Shorts title, a two-sentence description, and 3-5 hashtags.
''',
        schema=SeoPackage,
    )
