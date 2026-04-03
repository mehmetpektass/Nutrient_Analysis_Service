import sqlite3
from pathlib import Path

DB_PATH = Path("food.db")

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def search_food(query: str) -> dict | None:
    con = get_connection()
    cur = con.cursor()

    # Search with FTS
    cur.execute("""
        SELECT f.*
        FROM foods_fts
        JOIN foods f ON foods_fts.rowid = f.fdc_id
        WHERE foods_fts MATCH ?
        ORDER BY rank
        LIMIT 1
    """, (query,))

    row = cur.fetchone()
    con.close()

    if not row:
        return None

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

def search_food_with_fallback(query: str) -> dict | None:
    result = search_food(query)
    if result:
        return result

    first_word = query.split()[0]
    if first_word != query:
        result = search_food(first_word)
        if result:
            return result

    return None