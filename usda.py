import json
import sqlite3
import os
import sys
import zipfile

DB_PATH = 'food.db'

FOUNDATION_ZIP = "FoodData_Central_foundation_food_json_2025-12-18.zip"
SR_LEGACY_ZIP = "FoodData_Central_sr_legacy_food_json_2018-04.zip"

NUTRIENT_IDS = {
    1008: "kcal",
    1003: "protein",
    1004: "fat",
    1005: "carbs",
    1079: "fiber",    
    1063: "sugar",
    2000: "sugar",
    1258: "saturated_fat",
    1093: "sodium",
    1087: "calcium",
    1089: "iron",
    1092: "potassium",
    1162: "vitamin_c",
}

def extract_json(zip_path: str) -> dict:
    print(f"Extracting {zip_path}...")
    with zipfile.ZipFile(zip_path) as z:
        json_filename = next(n for n in z.namelist() if n.endswith(".json"))
        with z.open(json_filename) as f:
            return json.load(f)

def parse_foods(data: dict) -> list[dict]:
    foods = []
    raw_foods = data.get("FoundationFoods") or data.get("SRLegacyFoods", [])

    for food in raw_foods:
        name = food.get("description", "").strip().lower()
        if not name:
            continue

        nutrients = {}
        for n in food.get("foodNutrients", []):
            nutrient_id = n.get("nutrient", {}).get("id")
            amount = round(n.get("amount", 0), 2)

            if nutrient_id == 1008:
                nutrients["kcal"] = amount
            elif nutrient_id == 1003:
                nutrients["protein"] = amount
            elif nutrient_id == 1004:
                nutrients["fat"] = amount
            elif nutrient_id == 1005:
                nutrients["carbs"] = amount
            elif nutrient_id == 1079:
                nutrients["fiber"] = amount
            elif nutrient_id in (1063, 2000):
                nutrients["sugar"] = amount
            elif nutrient_id == 1258:
                nutrients["saturated_fat"] = amount
            elif nutrient_id == 1093:
                nutrients["sodium"] = amount
            elif nutrient_id == 1087:
                nutrients["calcium"] = amount
            elif nutrient_id == 1089:
                nutrients["iron"] = amount
            elif nutrient_id == 1092:
                nutrients["potassium"] = amount
            elif nutrient_id == 1162:
                nutrients["vitamin_c"] = amount

        if "kcal" not in nutrients:
            p = nutrients.get("protein", 0)
            f = nutrients.get("fat", 0)
            c = nutrients.get("carbs", 0)
            if p == 0 and f == 0 and c == 0:
                continue
            nutrients["kcal"] = round((p * 4) + (f * 9) + (c * 4), 1)

        foods.append({
            "fdc_id":        food.get("fdcId"),
            "name":          name,
            "kcal":          nutrients.get("kcal", 0),
            "protein":       nutrients.get("protein", 0),
            "fat":           nutrients.get("fat", 0),
            "carbs":         nutrients.get("carbs", 0),
            "fiber":         nutrients.get("fiber", 0),
            "sugar":         nutrients.get("sugar", 0),
            "saturated_fat": nutrients.get("saturated_fat", 0),
            "sodium":        nutrients.get("sodium", 0),
            "calcium":       nutrients.get("calcium", 0),
            "iron":          nutrients.get("iron", 0),
            "potassium":     nutrients.get("potassium", 0),
            "vitamin_c":     nutrients.get("vitamin_c", 0),
        })

    return foods

def build_db(foods: list[dict]):
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        print(f"Existing {DB_PATH} removed")
    
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    
    cur.executescript("""
        CREATE TABLE foods (
            fdc_id        INTEGER PRIMARY KEY,
            name          TEXT NOT NULL,
            kcal          REAL DEFAULT 0,
            protein       REAL DEFAULT 0,
            fat           REAL DEFAULT 0,
            carbs         REAL DEFAULT 0,
            fiber         REAL DEFAULT 0,
            sugar         REAL DEFAULT 0,
            saturated_fat REAL DEFAULT 0,
            sodium        REAL DEFAULT 0,
            calcium       REAL DEFAULT 0,
            iron          REAL DEFAULT 0,
            potassium     REAL DEFAULT 0,
            vitamin_c     REAL DEFAULT 0
        );

        CREATE VIRTUAL TABLE foods_fts USING fts5(
            name,
            content='foods',
            content_rowid='fdc_id'
        );
    """)
    
    cur.executemany(
        """INSERT INTO foods VALUES (
            :fdc_id, :name, :kcal, :protein, :fat, :carbs,
            :fiber, :sugar, :saturated_fat, :sodium,
            :calcium, :iron, :potassium, :vitamin_c
        )""",
        foods
    )
    
    cur.execute("INSERT INTO foods_fts(foods_fts) VALUES('rebuild')")
    con.commit()
    con.close()
    print(f"Done. {len(foods)} foods written to {DB_PATH}.")

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con



def get_candidates(query: str, limit: int = 40) -> list[dict]:
    """Get closest candidates from database without filtering (For reranker)"""
    con = get_connection()
    cur = con.cursor()
    
    if not query or len(query.strip()) < 2:
        return []

    words = query.strip().split()
    candidates = {}

    fts_query = " OR ".join(f"{word}*" for word in words)
    try:
        cur.execute(
            """
            SELECT f.* FROM foods_fts 
            JOIN foods f ON foods_fts.rowid = f.fdc_id 
            WHERE foods_fts MATCH ? ORDER BY rank LIMIT ?
            """, (fts_query, limit)
        )
        for row in cur.fetchall():
            candidates[row["fdc_id"]] = dict(row)
    except sqlite3.OperationalError:
        pass

    # 2. LIKE search (If FTS5 returns empty, try each word individually)
    if len(candidates) < limit:
        for word in words:
            like_query = f"%{word}%"
            cur.execute("SELECT * FROM foods WHERE name LIKE ? LIMIT ?", (like_query, limit))
            for row in cur.fetchall():
                if row["fdc_id"] not in candidates:
                    candidates[row["fdc_id"]] = dict(row)
                    if len(candidates) >= limit: break
            if len(candidates) >= limit: break

    con.close()
    return list(candidates.values())[:limit]


def main():
    all_foods = []
    for zip_path in [FOUNDATION_ZIP, SR_LEGACY_ZIP]:
        if not os.path.exists(zip_path):
            print(f"WARNING: {zip_path} not found, skipping.")
            continue
        data = extract_json(zip_path)
        foods = parse_foods(data)
        print(f"  → {len(foods)} foods parsed from {zip_path}")
        all_foods.extend(foods)

    if not all_foods:
        print("ERROR: No food data found. Download the USDA zip files first.")
        sys.exit(1)
        
    seen = set()
    unique_foods = []
    for f in all_foods:
        if f["fdc_id"] not in seen:
            seen.add(f["fdc_id"])
            unique_foods.append(f)

    build_db(unique_foods)

if __name__ == "__main__":
    main()