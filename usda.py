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
]

BONUS_KEYWORDS = ["raw", "cooked", "boiled", "roasted", "baked", "whole", "fresh"]

# Singular → plural or different forms
WORD_VARIANTS = {
    "egg":    ["egg", "eggs"],
    "eggs":   ["egg", "eggs"],
    "oil":    ["oil", "oils"],
    "rice":   ["rice"],
    "milk":   ["milk"],
    "butter": ["butter"],
    "salmon": ["salmon"],
    "chicken":["chicken"],
}

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _score(name: str, query_words: list[str]) -> float:
    name_lower = name.lower()
    first_segment = name_lower.split(",")[0].strip()
    score = 0

    # Most important rule: big bonus if name starts with first query word
    for variant in WORD_VARIANTS.get(query_words[0], [query_words[0]]):
        if first_segment == variant or first_segment.startswith(variant + " "):
            score -= 50
            break

    # Bonus if all query words appear as whole words in the name
    for word in query_words:
        variants = WORD_VARIANTS.get(word, [word])
        for v in variants:
            pattern = r'(^|[\s,])' + re.escape(v) + r'($|[\s,])'
            if re.search(pattern, name_lower):
                score -= 10
                break

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
    words = query.lower().split()
    rows = []

    first = words[0]
    variants = WORD_VARIANTS.get(first, [first])

    # 1. Name starts with main word + other words also appear
    for v in variants:
        conditions = " AND ".join(["name LIKE ?"] * len(words))
        params = [f"{v}%"] + [f"%{w}%" for w in words[1:]]
        if len(words) == 1:
            params = [f"{v}%"]
            conditions = "name LIKE ?"
        cur.execute(f"SELECT * FROM foods WHERE {conditions} LIMIT 40", params)
        rows = cur.fetchall()
        if rows:
            break

    # 2. All words appear anywhere in the name
    if not rows:
        conditions = " AND ".join(["name LIKE ?" for _ in words])
        params = [f"%{w}%" for w in words]
        cur.execute(f"SELECT * FROM foods WHERE {conditions} LIMIT 40", params)
        rows = cur.fetchall()

    # 3. Only first word — from the beginning
    if not rows:
        for v in variants:
            cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 40", (f"{v}%",))
            rows = cur.fetchall()
            if rows:
                break

    # 4. Only first word — anywhere
    if not rows:
        cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT 40", (f"%{first}%",))
        rows = cur.fetchall()

    con.close()

    if not rows:
        return None

    best = min(rows, key=lambda r: _score(r["name"], words))
    return _to_dict(best)