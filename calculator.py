# calculator.py (Parallel Processing Version)
import asyncio
from usda import get_candidates
from vision import rerank_candidates

NUTRIENT_FIELDS = [
    "kcal", "protein", "fat", "carbs", "fiber", "sugar",
    "saturated_fat", "sodium", "calcium", "iron", "potassium", "vitamin_c",
]

def _blank_totals() -> dict:
    return {field: 0.0 for field in NUTRIENT_FIELDS}

def _scale_nutrition(nutrition: dict, grams: float) -> dict:
    factor = grams / 100
    return {field: round(nutrition[field] * factor, 1) for field in NUTRIENT_FIELDS}

async def _process_single_ingredient(item: dict, user_note: str) -> dict:
    """Helper function that processes a single ingredient and returns result (Will run in parallel)"""
    name = item["name"]
    search_query = item.get("db_query") or name
    grams = float(item["estimated_grams"])
    confidence = item.get("confidence", "medium")
    source = item.get("source", "visible")

    # 1. Cast a wide net and collect candidates (This operation takes seconds)
    candidates = get_candidates(search_query, limit=15)

    if not candidates:
        return {"status": "not_found", "name": name}

    # 2. Ask Gemini Judge (API request - Actual waiting time is here)
    best_fdc_id = await rerank_candidates(search_query, user_note, candidates)

    if not best_fdc_id:
        return {"status": "not_found", "name": name}

    # 3. Find the candidate chosen by the judge from the list
    best_nutrition = next((c for c in candidates if c["fdc_id"] == best_fdc_id), None)

    if not best_nutrition:
        return {"status": "not_found", "name": name}

    # 4. Prepare row data
    row = {
        "name": name,
        "search_query": search_query,
        "matched_to": best_nutrition["name"],
        "grams": grams,
        "confidence": confidence,
        "source": source,
    }
    row.update(_scale_nutrition(best_nutrition, grams))
    return {"status": "success", "row": row}

async def calculate(ingredients: list[dict], user_note: str = "") -> dict:
    breakdown = []
    not_found = []
    totals = _blank_totals()

    # MAGIC HAPPENS HERE: Process all ingredients at the same time (in parallel)!
    tasks = [_process_single_ingredient(item, user_note) for item in ingredients]
    results = await asyncio.gather(*tasks)

    # Collect results
    for result in results:
        if result["status"] == "not_found":
            not_found.append(result["name"])
        elif result["status"] == "success":
            row = result["row"]
            breakdown.append(row)
            for key in NUTRIENT_FIELDS:
                totals[key] += row[key]

    # Round totals
    for key in NUTRIENT_FIELDS:
        totals[key] = round(totals[key], 1)

    return {
        "totals": totals,
        "breakdown": breakdown,
        "not_found": not_found,
    }