import asyncio
from usda import get_candidates
from vision import batch_rerank_candidates
from cache import get_cached_id, set_cached_id

NUTRIENT_FIELDS = [
    "kcal", "protein", "fat", "carbs", "fiber", "sugar",
    "saturated_fat", "sodium", "calcium", "iron", "potassium", "vitamin_c",
]

def _blank_totals() -> dict:
    return {field: 0.0 for field in NUTRIENT_FIELDS}

def _scale_nutrition(nutrition: dict, grams: float) -> dict:
    factor = grams / 100
    return {field: round(nutrition[field] * factor, 1) for field in NUTRIENT_FIELDS}

async def calculate(ingredients: list[dict], user_note: str = "") -> dict:
    breakdown = []
    not_found = []
    totals = _blank_totals()

    final_fdc_ids = {} # { "query": fdc_id }
    items_to_rerank = {} # { "query": [candidates] }

    # STEP 1: Check Cache & Gather Candidates locally
    for item in ingredients:
        search_query = item.get("db_query") or item["name"]
        
        # Is it in our lightning-fast cache?
        is_cached, cached_id = get_cached_id(search_query)
        if is_cached:
            final_fdc_ids[search_query] = cached_id
            continue
            
        # Not in cache, get candidates from local SQLite
        candidates = get_candidates(search_query, limit=15)
        if not candidates:
            final_fdc_ids[search_query] = None
        else:
            simplified = [{"fdc_id": c["fdc_id"], "name": c["name"]} for c in candidates]
            items_to_rerank[search_query] = simplified

    # STEP 2: Batch Rerank (Send all unknown items to LLM in ONE request)
    if items_to_rerank:
        rerank_results = await batch_rerank_candidates(items_to_rerank, user_note)
        
        # Save results to Cache & Final dictionary
        for query, candidates in items_to_rerank.items():
            best_id = rerank_results.get(query)
            final_fdc_ids[query] = best_id
            set_cached_id(query, best_id) # Learn for next time!

    # STEP 3: Build the final nutritional breakdown
    for item in ingredients:
        name = item["name"]
        search_query = item.get("db_query") or name
        grams = float(item["estimated_grams"])
        
        best_id = final_fdc_ids.get(search_query)
        
        if not best_id:
            not_found.append(name)
            continue
            
        # Fetch full nutritional data from local DB
        candidates = get_candidates(search_query, limit=40)
        best_nutrition = next((c for c in candidates if c["fdc_id"] == best_id), None)
        
        if not best_nutrition:
            not_found.append(name)
            continue

        row = {
            "name": name,
            "search_query": search_query,
            "matched_to": best_nutrition["name"],
            "grams": grams,
            "confidence": item.get("confidence", "medium"),
            "source": item.get("source", "visible"),
        }
        row.update(_scale_nutrition(best_nutrition, grams))
        breakdown.append(row)
        
        for key in NUTRIENT_FIELDS:
            totals[key] += row[key]

    for key in NUTRIENT_FIELDS:
        totals[key] = round(totals[key], 1)

    return {
        "totals": totals,
        "breakdown": breakdown,
        "not_found": not_found,
    }