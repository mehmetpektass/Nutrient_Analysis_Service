import sqlite3
import re
from pathlib import Path

DB_PATH = Path("food.db")

PENALTY_KEYWORDS = [
    "restaurant", "fast food", "kfc", "mcdonald", "burger king",
    "popeyes", "olive garden", "frozen", "breaded", "dry mix",
    "nuggets", "strips", "tenders", "roll", "links", "flavored",
    "seasoned", "custard", "eggplant", "butterhead", "buttermilk",
    "oscar mayer", "honey glazed", "noodles", "flour", "mashed",
    "snacks", "cake", "cakes", "cracker", "crackers", "candies", "cereal"
]

BONUS_KEYWORDS = ["raw", "cooked", "boiled", "roasted", "baked", "whole", "fresh","seeds", "nuts"]

DESCRIPTOR_WORDS = {
    "air", "fried", "airfried", "cooked", "grilled", "broiled", "braised", "roasted",
    "baked", "boiled", "steamed", "toasted", "sliced", "slice", "slices", "chopped", "diced",
    "fresh", "plain", "whole", "low", "fat", "fatfree", "free", "reduced", "light",
    "lean", "boneless", "skinless", "prepared", "recipe", "with", "without", "made",
    "from", "in", "and", "or", "of", "style", "canned", "frozen", "dry", "mix",
    "drained", "root", "removed", "kernels", "kernel", "salad", "cooking", "hotdog",
    "pitted", "white", "green", "red", "yellow", "black",
}

CATEGORY_TOKENS = {
    "fruit": {"banana", "blueberry", "blueberries", "grape", "orange", "apple", "berries", "berry"},
    "vegetable": {"broccoli", "pepper", "peppers", "bell", "lettuce", "tomato", "pickle", "pickles", "olive", "olives", "onion", "onions", "scallion", "mushroom", "mushrooms", "corn", "potato", "potatoes"},
    "meat": {"beef", "steak", "chicken", "salmon", "fish", "sunfish", "pork", "pepperoni", "sausage", "bacon", "frankfurter"},
    "dairy": {"milk", "cheese", "mozzarella", "cheddar", "parmesan", "cream", "yogurt", "butter"},
    "grain": {"rice", "oat", "oats", "oatmeal", "flour", "bread", "bun", "pasta", "pizza", "crust", "dough", "pancake"},
    "sauce": {"sauce", "syrup", "ketchup", "catsup", "mayo", "mayonnaise", "molasses", "ganache"},
    "oil": {"oil"},
    "nut_seed": {"almond", "almonds", "peanut", "peanuts", "pistachio", "pistachios", "walnut", "walnuts", "sesame", "pumpkin", "seed", "seeds"},
}

INCOMPATIBLE_CATEGORIES = {
    "fruit": {"meat", "vegetable", "oil"},
    "vegetable": {"meat", "fruit", "oil"},
    "meat": {"fruit", "vegetable", "oil", "sauce"},
    "sauce": {"meat", "fruit", "vegetable"},
    "oil": {"meat", "fruit", "vegetable"},
    "nut_seed": {"meat", "fruit", "vegetable"},
}

MEAL_INDICATOR_PHRASES = [
    " with ", " in ", "filled", "stuffed", "ravioli", "lasagna", "sandwich",
    "pizza hut", "denny", "wendy's", "burger king", "mcdonald", "carrabba", "applebee",
]

TOKEN_NORMALIZATIONS = {
    "eggs": "egg",
    "oils": "oil",
    "pistachios": "pistachio",
    "blueberries": "blueberry",
    "bananas": "banana",
    "peppers": "pepper",
    "olives": "olive",
    "pickles": "pickle",
    "scallions": "scallion",
    "mushrooms": "mushroom",
    "potatoes": "potato",
    "seeds": "seed",
    "rings": "ring",
    "cookies": "cookie",
}

# Singular → plural or different forms
WORD_VARIANTS = {
    "egg": ["egg", "eggs"],
    "oil": ["oil", "oils"],
    "rice": ["rice"],
    "milk": ["milk"],
    "butter": ["butter"],
    "banana": ["banana", "bananas"],
    "olive": ["olive", "olives"],
    "seed": ["seed", "seeds"],
    "onion": ["onion", "onions"],
    "pepper": ["pepper", "peppers"],
    "mushroom": ["mushroom", "mushrooms"],
    "pickle": ["pickle", "pickles"],
    "salmon": ["salmon"],
    "chicken": ["chicken"],
    "pistachio": ["pistachio", "pistachios"],
    "syrup": ["syrup", "syrups"],
}

QUERY_SYNONYMS = {
    "egg": ["whole egg", "egg, whole", "raw egg"],
    "butter": ["butter, salted", "butter, without salt"],
    "olive oil": ["oil, olive", "olive oil"],
    "pistachio": ["pistachio nuts", "nuts, pistachio"],
    "chicken breast": ["chicken breast", "breast meat"],
    "white rice": ["rice, white"],
}

PREFERRED_HEADWORDS = {
    "olive oil": ["oil"],
    "sugar syrup": ["syrup", "syrups"],
    "egg": ["egg"],
    "butter": ["butter"],
}

QUERY_SPECIFIC_BONUSES = {
    "chicken breast": ["meat only", "boneless", "skinless", "broilers or fryers"],
    "olive oil": ["oil, olive"],
    "sugar syrup": ["syrup, cane", "fruit syrup"],
}

QUERY_SPECIFIC_PENALTIES = {
    "chicken breast": ["sliced", "deli", "prepackaged", "fat-free", "mesquite", "roll", "tenders", "breaded"],
    "olive oil": ["mayonnaise", "anchovies"],
    "sugar syrup": ["popcorn", "sugar free", "chocolate", "fruit flavored"],
    "sesame seeds": ["snacks", "rice cakes", "crackers", "bun", "bread"],
}

NEGATIVE_PHRASES = [
    "substitute",
    "powder",
    "dry mix",
    "peanut butter",
    "buttermilk",
    "butterfinger",
    "eggplant",
    "egg roll",
    "egg rolls",
    "egg noodle",
    "egg noodles",
    "olive garden",
    "olive loaf",
    "yogurt covered",
]

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _normalize_token(token: str) -> str:
    token = re.sub(r"[^a-z0-9]+", "", token.lower())
    return TOKEN_NORMALIZATIONS.get(token, token)

def _normalize_query(query: str) -> list[str]:
    words = [_normalize_token(word) for word in query.split()]
    return [word for word in words if word]

def _whole_word_present(text: str, word: str) -> bool:
    pattern = r"(^|[\s,()/-])" + re.escape(word) + r"($|[\s,()/-])"
    return re.search(pattern, text) is not None

def _core_tokens(query_words: list[str]) -> list[str]:
    core = [word for word in query_words if word not in DESCRIPTOR_WORDS]
    return core or query_words

def _query_categories(tokens: list[str]) -> set[str]:
    categories = set()
    for token in tokens:
        for category, words in CATEGORY_TOKENS.items():
            if token in words:
                categories.add(category)
    return categories

def _candidate_categories(name_lower: str) -> set[str]:
    tokens = {_normalize_token(token) for token in re.findall(r"[a-z0-9]+", name_lower)}
    categories = set()
    for category, words in CATEGORY_TOKENS.items():
        if tokens & words:
            categories.add(category)
    return categories

def _phrase_bonus(name_lower: str, core_tokens: list[str]) -> float:
    score = 0.0
    if len(core_tokens) >= 2:
        for left, right in zip(core_tokens, core_tokens[1:]):
            phrase = f"{left} {right}"
            if phrase in name_lower:
                score -= 35
    return score

def _head_token(core_tokens: list[str]) -> str:
    return core_tokens[-1] if core_tokens else ""

def _score(name: str, query_words: list[str]) -> float:
    name_lower = name.lower()
    first_segment = name_lower.split(",")[0].strip()
    query_text = " ".join(query_words)
    core_tokens = _core_tokens(query_words)
    head_token = _head_token(core_tokens)
    query_categories = _query_categories(core_tokens)
    candidate_categories = _candidate_categories(name_lower)
    score = 0

    # Most important rule: big bonus if name starts with first query word
    anchor = core_tokens[0] if core_tokens else query_words[0]
    for variant in WORD_VARIANTS.get(anchor, [anchor]):
        if first_segment == variant or first_segment.startswith(variant + " "):
            score -= 50
            break

    # Strong preference for candidates containing all core words.
    for word in core_tokens:
        variants = WORD_VARIANTS.get(word, [word])
        found = False
        for v in variants:
            if _whole_word_present(name_lower, v):
                score -= 18
                found = True
                break
        if not found:
            score += 90

    # Descriptor words should help lightly but never dominate.
    for word in query_words:
        if word in core_tokens:
            continue
        variants = WORD_VARIANTS.get(word, [word])
        if any(_whole_word_present(name_lower, v) for v in variants):
            score -= 3

    if name_lower == query_text:
        score -= 100
    elif query_text and query_text in name_lower:
        score -= 30

    if head_token and _whole_word_present(name_lower, head_token):
        score -= 35
    elif head_token:
        score += 110

    score += _phrase_bonus(name_lower, core_tokens)

    for synonym in QUERY_SYNONYMS.get(query_text, []):
        if synonym in name_lower:
            score -= 35

    # Simple ingredient queries should not resolve to branded or complete meals.
    if core_tokens and any(phrase in name_lower for phrase in MEAL_INDICATOR_PHRASES):
        score += 80
    if core_tokens and ("'" in name_lower or name_lower.startswith("fast foods")):
        score += 60

    # Prefer category-compatible candidates.
    for category in query_categories:
        incompatible = INCOMPATIBLE_CATEGORIES.get(category, set())
        if candidate_categories & incompatible:
            score += 120

    if "sauce" in query_categories and "sauce" not in candidate_categories:
        score += 120
    if "oil" in query_categories and "oil" not in candidate_categories:
        score += 120

    # Avoid compound-food traps like banana pepper, peanut butter vs butter, etc.
    if "banana" in core_tokens and "pepper" in candidate_categories:
        score += 140
    if "pepper" in core_tokens and "banana" in name_lower and "pepper" not in core_tokens:
        score += 120
    if "peanut" in core_tokens and "peanut" not in name_lower:
        score += 140
    if "pumpkin" in core_tokens and "pumpkin" not in name_lower:
        score += 120
    if "white" in query_words and "sugar" in core_tokens and "sugar" not in name_lower:
        score += 160
    if "air" in query_words and "popcorn" in name_lower:
        score += 160
    if "steamed" in query_words and "taro" in name_lower:
        score += 140
    if "pizza" in core_tokens and any(term in name_lower for term in ("pizza hut", "denny", "carrabba")):
        score += 160
    if "sauce" in core_tokens and any(term in name_lower for term in ("ravioli", "pulled pork", "pizza hut")):
        score += 160

    preferred_heads = PREFERRED_HEADWORDS.get(query_text, [])
    if preferred_heads and not any(first_segment == head or first_segment.startswith(head + " ") for head in preferred_heads):
        score += 45

    for phrase in QUERY_SPECIFIC_BONUSES.get(query_text, []):
        if phrase in name_lower:
            score -= 25

    for phrase in QUERY_SPECIFIC_PENALTIES.get(query_text, []):
        if phrase in name_lower:
            score += 45

    for phrase in NEGATIVE_PHRASES:
        if phrase in name_lower:
            score += 60

    # Penalty
    for kw in PENALTY_KEYWORDS:
        if kw in name_lower:
            score += 30

    # Bonus
    for kw in BONUS_KEYWORDS:
        if kw in name_lower:
            score -= 8

    # Short name bonus
    score += len(name) * 0.05

    return score

def _collect_candidates(cur: sqlite3.Cursor, query_words: list[str]) -> list[sqlite3.Row]:
    rows_by_id: dict[int, sqlite3.Row] = {}
    core_tokens = _core_tokens(query_words)

    def add_rows(found_rows):
        for row in found_rows:
            rows_by_id[row["fdc_id"]] = row

    if query_words:
        fts_tokens = core_tokens or query_words
        fts_query = " ".join(f"{word}*" for word in fts_tokens)
        try:
            cur.execute(
                """
                SELECT f.*
                FROM foods_fts
                JOIN foods f ON foods_fts.rowid = f.fdc_id
                WHERE foods_fts MATCH ?
                LIMIT 80
                """,
                (fts_query,),
            )
            add_rows(cur.fetchall())
        except sqlite3.OperationalError:
            pass

        conditions = " AND ".join(["name LIKE ?"] * len(fts_tokens))
        cur.execute(
            f"SELECT * FROM foods WHERE {conditions} LIMIT 80",
            [f"%{word}%" for word in fts_tokens],
        )
        add_rows(cur.fetchall())

        anchor_tokens = core_tokens or query_words
        for anchor in anchor_tokens[:2]:
            for variant in WORD_VARIANTS.get(anchor, [anchor]):
                cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 80", (f"{variant}%",))
                add_rows(cur.fetchall())
                cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 80", (f"%{variant}%",))
                add_rows(cur.fetchall())

        if len(core_tokens) >= 2:
            phrase = " ".join(core_tokens[:2])
            cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 80", (f"%{phrase}%",))
            add_rows(cur.fetchall())

        first = anchor_tokens[0]
        for variant in WORD_VARIANTS.get(first, [first]):
            cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 80", (f"{variant}%",))
            add_rows(cur.fetchall())
            cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 80", (f"%{variant}%",))
            add_rows(cur.fetchall())

    return list(rows_by_id.values())

def _to_dict(row) -> dict:
    return {
        "fdc_id":        row["fdc_id"],
        "name":          row["name"],
        "kcal":          row["kcal"],
        "protein":       row["protein"],
        "fat":           row["fat"],
        "carbs":         row["carbs"],
        "fiber":         row["fiber"],
        "sugar":         row["sugar"],
        "saturated_fat": row["saturated_fat"],
        "sodium":        row["sodium"],
        "calcium":       row["calcium"],
        "iron":          row["iron"],
        "potassium":     row["potassium"],
        "vitamin_c":     row["vitamin_c"],
    }

def search_food(query: str) -> dict | None:
    con = get_connection()
    cur = con.cursor()
    words = _normalize_query(query)

    cur.execute("SELECT * FROM foods WHERE lower(name) = ? LIMIT 1", (query.strip().lower(),))
    exact_row = cur.fetchone()
    if exact_row:
        con.close()
        return _to_dict(exact_row)

    rows = _collect_candidates(cur, words)

    con.close()

    if not rows:
        return None

    best = min(rows, key=lambda r: _score(r["name"], words))
    return _to_dict(best)
