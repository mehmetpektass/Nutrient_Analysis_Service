from usda import search_food

def calculate(ingredients: list[dict]) -> dict:
    breakdown = []
    not_found = []

    totals = {
        "kcal":          0,
        "protein":       0,
        "fat":           0,
        "carbs":         0,
        "fiber":         0,
        "sugar":         0,
        "saturated_fat": 0,
        "sodium":        0,
        "calcium":       0,
        "iron":          0,
        "potassium":     0,
        "vitamin_c":     0,
    }

    for item in ingredients:
        name       = item["name"]
        grams      = float(item["estimated_grams"])
        confidence = item.get("confidence", "medium")

        try:
            nutrition = search_food(name)
        except Exception as e:
            print(f"[WARN] search_food failed for '{name}': {e}")
            not_found.append(name)
            continue

        if not nutrition:
            not_found.append(name)
            continue

        factor = grams / 100

        row = {
            "name":          name,
            "matched_to":    nutrition["name"],
            "grams":         grams,
            "confidence":    confidence,
            "kcal":          round(nutrition["kcal"]          * factor, 1),
            "protein":       round(nutrition["protein"]       * factor, 1),
            "fat":           round(nutrition["fat"]           * factor, 1),
            "carbs":         round(nutrition["carbs"]         * factor, 1),
            "fiber":         round(nutrition["fiber"]         * factor, 1),
            "sugar":         round(nutrition["sugar"]         * factor, 1),
            "saturated_fat": round(nutrition["saturated_fat"] * factor, 1),
            "sodium":        round(nutrition["sodium"]        * factor, 1),
            "calcium":       round(nutrition["calcium"]       * factor, 1),
            "iron":          round(nutrition["iron"]          * factor, 1),
            "potassium":     round(nutrition["potassium"]     * factor, 1),
            "vitamin_c":     round(nutrition["vitamin_c"]     * factor, 1),
        }

        for key in totals:
            totals[key] += row[key]

        breakdown.append(row)

    for key in totals:
        totals[key] = round(totals[key], 1)

    return {
        "totals":    totals,
        "breakdown": breakdown,
        "not_found": not_found,
    }