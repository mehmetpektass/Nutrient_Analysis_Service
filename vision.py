import json
import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL")

client = genai.Client(api_key=GEMINI_API_KEY)


SYSTEM_PROMPT = """
You are a nutrition analysis assistant. Analyze the food image carefully.

Your job:
- Identify every visible ingredient separately
- Estimate the weight in grams for each ingredient realistically
- If the user provides notes (e.g. "very oily", "there is hidden chicken under the rice"), adjust your analysis accordingly
- Use simple English food names suitable for a nutrition database (e.g. "chicken breast", "white rice", "olive oil")
- Be conservative with gram estimates

Rules:
- Never combine ingredients (e.g. do not say "rice with chicken", say them separately)
- Do not include drinks or non-food items
- If you are unsure about an ingredient, still include it with confidence "low"

Respond ONLY with valid JSON matching this exact schema, no explanation, no markdown:
{
  "dish_name": "string",
  "ingredients": [
    {
      "name": "string",
      "estimated_grams": number,
      "confidence": "low" | "medium" | "high"
    }
  ]
}
"""

async def analyze_image(image_bytes: bytes, user_note: str = "") -> dict:
    prompt = SYSTEM_PROMPT
    
    if user_note:
        prompt += f"\n\nUser note about this food: {user_note}"

    image_part = {
        "mime_type": "image/jpeg",
        "data": image_bytes
    }
    
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                types.Part.from_text(text=prompt),
            ]
        )
    )
    raw = response.text.strip()
    
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)

    return json.loads(raw.strip())

