from openai import OpenAI
from app.config import OPENAI_API_KEY, OPENAI_TEXT_MODEL

client = OpenAI(api_key=OPENAI_API_KEY)

def structured_response(*, instructions: str, prompt: str, schema):
    response = client.responses.parse(
        model=OPENAI_TEXT_MODEL,
        instructions=instructions,
        input=prompt,
        text_format=schema,
    )
    if response.output_parsed is None:
        raise RuntimeError("The model returned no structured output.")
    return response.output_parsed
