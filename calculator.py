from usda import search_food

NUTRIENT_FIELDS = [
    "kcal",
    "protein",
    "fat",
    "carbs",
    "fiber",
    "sugar",
    "saturated_fat",
    "sodium",
    "calcium",
    "iron",
    "potassium",
    "vitamin_c",
]

QUERY_OVERRIDES = [
    (("brioche bun", "hamburger bun", "burger bun"), "rolls, hamburger or hotdog, plain"),
    (("beef patty", "ground beef patty", "cooked beef patty"), "beef, ground, 95% lean meat / 5% fat, patty, cooked, broiled"),
    (("salmon fillet", "cooked salmon", "grilled salmon", "glazed salmon", "salmon"), "fish, salmon, atlantic, farmed, cooked, dry heat"),
    (("banana", "banana slices", "sliced banana"), "bananas, raw"),
    (("cheddar cheese slice", "cheddar slice", "cheddar cheese"), "cheese, cheddar"),
    (("lettuce leaf", "leaf lettuce", "lettuce"), "lettuce, iceberg, raw"),
    (("dill pickle slices", "pickle slices", "pickles", "dill pickles"), "pickles, cucumber, dill or kosher dill"),
    (("tomato ketchup", "ketchup", "catsup"), "catsup"),
    (("sliced tomato", "tomato slice", "tomato"), "tomato, roma"),
    (("regular mayonnaise", "mayonnaise"), "salad dressing, mayonnaise, regular"),
    (("soy sauce", "shoyu", "tamari"), "soy sauce made from soy and wheat (shoyu)"),
    (("green onion", "green onions", "scallion", "scallions", "spring onion", "spring onions", "chopped green onions"), "green onion, (scallion), bulb and greens, root removed, raw"),
    (("molasses", "grape molasses", "blackstrap molasses", "pekmez", "grape pekmez"), "molasses"),
    (("blueberries", "fresh blueberries", "blueberry"), "blueberries, raw"),
    (("peanut butter",), "peanut butter, creamy"),
    (("sesame seeds", "sesame seed"), "seeds, sesame seeds, whole, roasted and toasted"),
    (("bell pepper", "bell peppers", "sliced peppers", "sliced bell peppers"), "peppers, sweet, green, raw"),
    (("onion rings", "fried onion rings"), "onion rings, breaded, par fried, frozen, prepared, heated in oven"),
    (("cola", "cola soda", "cola 330ml"), "beverages, carbonated, cola, regular"),
    (("pizza crust", "pizza dough"), "pizza, cheese topping, regular crust, frozen, cooked"),
    (("pancake", "pancakes", "plain pancakes", "oatmeal pancake", "oat flour pancakes"), "pancakes, plain, prepared from recipe"),
    (("oat flour", "rolled oats", "oats", "oatmeal"), "oats"),
    (("egg", "eggs"), "egg, whole, raw, fresh"),
    (("milk",), "milk, whole, 3.25% milkfat"),
    (("french fries", "fries"), "potatoes, french fried, all types, salt not added in processing, frozen, as purchased"),
    (("phyllo dough",), "phyllo dough"),
    (("pistachios", "pistachio"), "nuts, pistachio nuts, raw"),
    (("walnuts", "walnut"), "nuts, walnuts, english"),
    (("butter",), "butter, without salt"),
    (("sugar free syrup",), "syrups, sugar free"),
    (("sugar syrup", "simple syrup", "sweet syrup"), "syrup, cane"),
]

DIRECT_NUTRITION_OVERRIDES = {
    "sweetener": {
        "name": "sweetener, zero calorie",
        "kcal": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
        "fiber": 0.0,
        "sugar": 0.0,
        "saturated_fat": 0.0,
        "sodium": 0.0,
        "calcium": 0.0,
        "iron": 0.0,
        "potassium": 0.0,
        "vitamin_c": 0.0,
    },
    "artificial sweetener": {
        "name": "sweetener, zero calorie",
        "kcal": 0.0,
        "protein": 0.0,
        "fat": 0.0,
        "carbs": 0.0,
        "fiber": 0.0,
        "sugar": 0.0,
        "saturated_fat": 0.0,
        "sodium": 0.0,
        "calcium": 0.0,
        "iron": 0.0,
        "potassium": 0.0,
        "vitamin_c": 0.0,
    },
}


def _blank_totals() -> dict:
    return {field: 0.0 for field in NUTRIENT_FIELDS}


def _round_nutrients(row: dict) -> dict:
    for field in NUTRIENT_FIELDS:
        row[field] = round(row[field], 1)
    return row


def _scale_nutrition(nutrition: dict, grams: float) -> dict:
    factor = grams / 100
    return {field: round(nutrition[field] * factor, 1) for field in NUTRIENT_FIELDS}


def _normalize_query(name: str, search_query: str) -> str:
    normalized = (search_query or name).strip().lower()

    if "baklava" in normalized:
        return normalized

    for aliases, canonical in QUERY_OVERRIDES:
        if normalized == canonical.lower():
            return canonical
        if normalized in aliases:
            return canonical
        if any(normalized.startswith(alias + " ") or normalized.endswith(" " + alias) for alias in aliases):
            return canonical
        if any(f" {alias} " in f" {normalized} " for alias in aliases):
            return canonical

    return search_query or name

def calculate(ingredients: list[dict]) -> dict:
    breakdown = []
    not_found = []

    totals = _blank_totals()

    for item in ingredients:
        name = item["name"]
        raw_search_query = item.get("db_query") or name
        search_query = _normalize_query(name, raw_search_query)
        grams = float(item["estimated_grams"])
        confidence = item.get("confidence", "medium")
        source = item.get("source", "visible")

        direct_override = DIRECT_NUTRITION_OVERRIDES.get(search_query.lower())
        if direct_override:
            row = {
                "name": name,
                "search_query": search_query,
                "matched_to": direct_override["name"],
                "grams": grams,
                "confidence": confidence,
                "source": source,
            }
            row.update(_scale_nutrition(direct_override, grams))
            for key in NUTRIENT_FIELDS:
                totals[key] += row[key]
            breakdown.append(row)
            continue

        try:
            nutrition = search_food(search_query)
        except Exception as e:
            print(f"[WARN] search_food failed for '{search_query}': {e}")
            not_found.append(name)
            continue

        if not nutrition:
            not_found.append(name)
            continue

        row = {
            "name":          name,
            "search_query":  search_query,
            "matched_to":    nutrition["name"],
            "grams":         grams,
            "confidence":    confidence,
            "source":        source,
        }
        row.update(_scale_nutrition(nutrition, grams))

        for key in NUTRIENT_FIELDS:
            totals[key] += row[key]

        breakdown.append(row)

    for key in NUTRIENT_FIELDS:
        totals[key] = round(totals[key], 1)

    return {
        "totals":    totals,
        "breakdown": breakdown,
        "not_found": not_found,
    }
