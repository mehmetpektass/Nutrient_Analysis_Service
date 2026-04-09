import json
import os
import asyncio
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
PRIMARY_MODEL = os.getenv("GEMINI_MODEL")
FALLBACK_MODEL = os.getenv("FALLBACK_MODEL")

client = genai.Client(api_key=GEMINI_API_KEY)

SYSTEM_PROMPT = """
You are an expert culinary and nutrition analysis assistant. Analyze the food image and user notes carefully.

YOUR ABSOLUTE PRIMARY DIRECTIVE:
NEVER output a finished dish, a recipe, or a composite meal as a single ingredient. You MUST DECOMPOSE every dish into its fundamental raw ingredients.

- BAD OUTPUTS: "Hamburger", "Orange Chicken", "Tiramisu", "Pizza", "Pancakes", "Walnut Baklava".
- GOOD OUTPUTS: "Hamburger Bun", "Ground Beef", "Cheddar Cheese", "Chicken Breast", "Cornstarch", "Soy Sauce", "Mascarpone", "Ladyfingers", "Flour", "Eggs", "Milk", "Phyllo dough", "Walnuts", "Butter", "Sugar Syrup".

Your job step-by-step:
1. Identify the dish in the image.
2. Mentally break it down into the raw ingredients needed to cook it.
3. Estimate the weight in grams for each RAW ingredient realistically based on the portion size.
4. Output ONLY those raw ingredients.
5. Produce a nutrition-oriented database search term (`db_query`) for each RAW ingredient.

Rules:
- CORRECT ANY TYPOS from the user note (e.g., "tramisu" -> "tiramisu" -> then decompose).
- If the user notes a substitution, output the substituted raw ingredient.
- If a dish is fried, include the cooking oil as a separate ingredient.
- USDA DATABASE AWARENESS & MANDATORY SUBSTITUTION: The `db_query` you generate will be directly searched in the US-centric USDA database. Foreign, cultural, or branded ingredients (e.g., "Halloumi", "Sucuk") DO NOT EXIST. You MUST translate them into the closest generic US-equivalent (e.g., "Halloumi" -> "Fontina cheese"). If you fail to substitute, the system will crash.
- SMART DATABASE QUERIES (CRITICAL): Generate a `db_query` that is most likely to find a direct match in the USDA FoodData Central.
  1. ADJECTIVES: Use condition adjectives ONLY when the cooking state matters (e.g., "roasted almonds", "boiled potato"). Do NOT force "raw" or "boiled" onto basic liquids, dairy, sugars, or powders (e.g., use "whole milk", "salt", "flour", "honey").
  2. PLURALS VS SINGULARS: Use plurals IF the item is naturally tiny and eaten in bulk (e.g., "blueberries", "oats", "strawberries", "pistachios"). Use singular for large distinct items (e.g., "apple", "egg", "chicken breast").
  3. STRIP SHAPES: Remove physical cuts or shapes (e.g., "diced", "sliced", "chips", "chunks"). For example, "semi-sweet chocolate chips" MUST become "semisweet chocolate".

- Respond ONLY with valid JSON matching this exact schema:
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

BATCH_RERANK_PROMPT = """
You are an expert nutritionist and database specialist.
User's overall cooking note: "{user_note}"
(CRITICAL RULE: The user note might be about a completely different part of the dish. ONLY apply this note to a specific ingredient if it logically affects it. Completely ignore dessert notes when evaluating vegetables/meat, etc.)

Here is a JSON dictionary where keys are ingredient search queries, and values are lists of candidate foods from the USDA database (ID and Name):
{batch_data_json}

Your task:
1. For EACH ingredient key, select the SINGLE best fdc_id from its candidate list.
2. Prefer generic, basic, raw, or unbranded whole foods.
3. If an ingredient is cultural/specific, translate it to the closest generic US-equivalent.
4. Return null ONLY if all candidates for that specific ingredient are 100% unrelated.

Respond ONLY with a valid JSON object matching this exact schema (keys must match the input keys):
{{
  "query_1": integer or null,
  "query_2": integer or null
}}
"""

async def _generate_with_fallback(contents) -> tuple[str, str]:
    """Returns the response text and the name of the model used."""
    
    # Reduce creativity, force logic and rule adherence
    req_config = types.GenerateContentConfig(
        temperature=0.1, 
        response_mime_type="application/json",
    )

    try:
        response = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: client.models.generate_content(
                model=PRIMARY_MODEL,
                contents=contents,
                config=req_config,
            )
        )
        return response.text, PRIMARY_MODEL
    except Exception as e:
        print(f"\n[WARNING] Primary Model ({PRIMARY_MODEL}) failed: {e}. Switching to Fallback...\n")
        
        await asyncio.sleep(2) 
        
        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.models.generate_content(
                    model=FALLBACK_MODEL,
                    contents=contents,
                    config=req_config 
                )
            )
            return response.text, FALLBACK_MODEL
        except Exception as backup_error:
            print(f"\n[CRITICAL ERROR] Fallback Model ({FALLBACK_MODEL}) also failed: {backup_error}")
            raise backup_error
        

async def analyze_image(image_bytes: bytes, user_note: str = "", mime_type: str = "image/jpeg") -> dict:
    prompt = SYSTEM_PROMPT
    if user_note:
        prompt += f"\n\nUser note about this food: {user_note}"
    
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
        types.Part.from_text(text=prompt),
    ]

    raw, used_model = await _generate_with_fallback(contents)
    raw = raw.strip()
    
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)

    result = json.loads(raw.strip())
    result["model_used"] = used_model 
    return result

async def batch_rerank_candidates(batch_data: dict, user_note: str) -> dict:
    """Sends multiple candidate lists to Gemini in a single request."""
    if not batch_data:
        return {}
        
    prompt = BATCH_RERANK_PROMPT.format(
        user_note=user_note,
        batch_data_json=json.dumps(batch_data, indent=2)
    )

    raw, _ = await _generate_with_fallback(prompt)
    raw = raw.strip()
    
    if raw.startswith("```"):
        lines = raw.split("\n")
        lines = [l for l in lines if not l.startswith("```")]
        raw = "\n".join(lines)

    try:
        return json.loads(raw.strip())
    except Exception as e:
        print(f"[WARN] Batch Reranker failed to parse JSON: {e}")
        return {}