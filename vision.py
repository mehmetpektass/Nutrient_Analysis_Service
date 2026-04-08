import json
import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL", "gemini-1.5-flash")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are an expert culinary and nutrition analysis assistant. Analyze the food image and user notes carefully.

YOUR ABSOLUTE PRIMARY DIRECTIVE:
NEVER output a finished dish, a recipe, or a composite meal as a single ingredient. You MUST DECOMPOSE every dish into its fundamental raw ingredients.

- BAD OUTPUTS (DO NOT DO THIS): "Hamburger", "Orange Chicken", "Tiramisu", "Pizza", "Pancakes", "Walnut Baklava".
- GOOD OUTPUTS (DO THIS): "Hamburger Bun", "Ground Beef", "Cheddar Cheese", "Chicken Breast", "Cornstarch", "Soy Sauce", "Mascarpone", "Ladyfingers", "Flour", "Eggs", "Milk", "Phyllo dough", "Walnuts", "Butter", "Sugar Syrup".

Your job step-by-step:
1. Identify the dish in the image.
2. Mentally break it down into the raw ingredients needed to cook it.
3. Estimate the weight in grams for each RAW ingredient realistically based on the portion size.
4. Output ONLY those raw ingredients.
5. Produce a nutrition-oriented database search term (`db_query`) for each RAW ingredient (e.g., "raw ground beef", "wheat flour", "raw egg").

Rules:
- CORRECT ANY TYPOS from the user note (e.g., "tramisu" -> "tiramisu" -> then decompose into ingredients).
- If the user notes a substitution (e.g., "used oats instead of flour"), output the substituted raw ingredient.
- If a dish is fried, include the cooking oil as a separate ingredient (e.g., "olive oil", "canola oil").
- If there is a sauce, decompose the sauce into base components if possible, or use basic generic sauce names.
- Do not include drinks or non-food items unless specifically requested in the user note.
- DATABASE AWARENESS: The `db_query` you generate will be directly searched in the USDA FoodData Central database. 
If an ingredient is highly specific, foreign, cultural, regional, or branded, it likely WILL NOT be found. 
You MUST translate it into the closest generic US-equivalent for the `db_query` field (e.g., translate a specific cultural cheese to "cream cheese" or "hard cheese", translate a specific Asian hot sauce to "hot chili sauce",
translate a regional flatbread to "flatbread" or "pita"). Keep the original cultural name in the `name` field for the user to see, but use the generic US term for the `db_query`.

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


RERANK_PROMPT = """
You are an expert nutritionist and database specialist.
The user is eating an ingredient identified as: "{ingredient_name}"

User's overall cooking note: "{user_note}"
(CRITICAL RULE: The user note might be about a completely different part of the dish or a dessert. ONLY apply this note to your decision if it logically affects "{ingredient_name}". If the note is about dessert and you are evaluating a vegetable like tomato, COMPLETELY IGNORE the note.)

Here is a list of candidate foods found in the USDA database (ID and Name):
{candidates_json}

Your task:
1. Select the SINGLE best match for what the user is actually eating.
2. Prefer generic, basic, raw, or unbranded whole foods over obscure items.
3. NEVER return null if there is a perfectly valid, safe, generic match in the list (e.g., if ingredient is "tomato", and "Tomatoes, raw" is in the list, you MUST select it!).
4. Return null ONLY if all candidates are 100% unrelated to "{ingredient_name}".

Respond ONLY with valid JSON matching this exact schema:
{{
  "best_fdc_id": integer or null
}}
"""


async def _generate_with_fallback(contents) -> str:
    """
    First tries PRIMARY_MODEL. If API fails due to overload (UNAVAILABLE etc.),
    waits 2 seconds and retries with FALLBACK_MODEL.
    """
    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=PRIMARY_MODEL,
                contents=contents
            )
        )
        return response.text
    except Exception as e:
        print(f"\n[WARNING] Primary Model ({PRIMARY_MODEL}) failed: {e}")
        print(f"[INFO] API may be busy. Waiting 2 seconds and switching to Fallback Model ({FALLBACK_MODEL})...\n")
        
        await asyncio.sleep(2) # Giving API time to breathe
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=FALLBACK_MODEL,
                    contents=contents
                )
            )
            return response.text
        except Exception as backup_error:
            print(f"\n[CRITICAL ERROR] Fallback Model ({FALLBACK_MODEL}) also failed: {backup_error}")
            raise backup_error # If both fail, raise the error (FastAPI will return 500)

async def analyze_image(image_bytes: bytes, user_note: str = "", mime_type: str = "image/jpeg") -> dict:
    prompt = SYSTEM_PROMPT
    if user_note:
        prompt += f"\n\nUser note about this food: {user_note}"
    
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        types.Part.from_text(text=prompt),
    ]

    # Calling smart fallback helper instead of directly calling the function
    raw = await _generate_with_fallback(contents)
    raw = raw.strip()
    
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)

    return json.loads(raw.strip())

async def rerank_candidates(ingredient_name: str, user_note: str, candidates: list[dict]) -> int | None:
    simplified_candidates = [{"fdc_id": c["fdc_id"], "name": c["name"]} for c in candidates]
    
    prompt = RERANK_PROMPT.format(
        ingredient_name=ingredient_name,
        user_note=user_note,
        candidates_json=json.dumps(simplified_candidates, indent=2)
    )

    # Also calling smart fallback helper for rerank operation
    raw = await _generate_with_fallback(prompt)
    raw = raw.strip()
    
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)

    try:
        result = json.loads(raw.strip())
        return result.get("best_fdc_id")
    except Exception as e:
        print(f"[WARN] Reranker failed to parse JSON: {e}")
        return None