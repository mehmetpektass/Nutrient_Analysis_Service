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
- Identify the final ingredients that are actually present in the food
- Estimate the weight in grams for each ingredient realistically
- If the user provides notes (e.g. "very oily", "there is hidden chicken under the rice", "made with sweetener instead of sugar"), modify the ingredient list accordingly
- Use simple English ingredient names suitable for a nutrition database (e.g. "chicken breast", "white rice", "olive oil", "blueberries")
- Produce a nutrition-oriented database search term for each ingredient when needed
- Be conservative with gram estimates

Rules:
- Output ingredients, not finished dishes or recipes
- Never combine ingredients (e.g. do not say "rice with chicken", say them separately)
- Do not include drinks or non-food items
- If the user note mentions extra food items not clearly visible, include them
- If the user note changes the recipe, replace the original ingredient with the modified one
- Do not keep both the original and replacement ingredient unless the user clearly says both are used
- If a hidden or user-reported food is a composite dish, decompose it into likely ingredients instead of outputting the dish name itself
- Prefer "walnuts", "phyllo dough", "butter", "syrup" over "walnut baklava" as a single ingredient
- Prefer "pizza dough", "mozzarella cheese", "tomato sauce" over "pizza" as a single ingredient when ingredient decomposition is possible
- If the user says "used oats instead of flour", include oats or oat flour and do not include flour
- If the user says "used sweetener instead of sugar", include sweetener or sugar-free syrup and do not include sugar
- If the user says "used butter generously", increase the butter amount instead of inventing a separate dish
- Break composite foods into plausible ingredients whenever possible
- Keep `name` human-readable, but make `db_query` optimized for nutrition lookup
- Examples:
  - Pancakes made with oats instead of flour: include ingredients like "oats", "egg", "milk", "blueberries", "sugar free syrup"
  - Baklava with hidden extra servings: include ingredients like "phyllo dough", "pistachios", "butter", "syrup" with source `user_note` or `both`
  - Salmon with molasses and butter: include "salmon fillet", "butter", "molasses"
- If you are unsure about an ingredient, still include it with confidence "low"

Respond ONLY with valid JSON matching this exact schema, no explanation, no markdown:
{
  "dish_name": "string",
  "ingredients": [
    {
      "name": "string",
      "db_query": "string",
      "estimated_grams": number,
      "confidence": "low" | "medium" | "high",
      "source": "visible" | "user_note" | "both"
    }
  ]
}
"""

async def analyze_image(image_bytes: bytes, user_note: str = "", mime_type: str = "image/jpeg") -> dict:
    prompt = SYSTEM_PROMPT
    
    if user_note:
        prompt += f"\n\nUser note about this food: {user_note}"
    
    response = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
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
