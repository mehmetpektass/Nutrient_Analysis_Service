import sqlite3

CACHE_DB = "cache.db"

def init_cache_db():
    """Initializes the cache database for USDA FDC IDs."""
    con = sqlite3.connect(CACHE_DB)
    cur = con.cursor()
    # fdc_id can be -1 to represent "Not Found" (null) so we don't keep searching for it
    cur.execute("""
        CREATE TABLE IF NOT EXISTS rerank_cache (
            search_query TEXT PRIMARY KEY,
            fdc_id INTEGER
        )
    """)
    con.commit()
    con.close()

def get_cached_id(search_query: str) -> tuple[bool, int | None]:
    """Returns (is_cached, fdc_id). If not cached, returns (False, None)."""
    try:
        con = sqlite3.connect(CACHE_DB)
        cur = con.cursor()
        cur.execute("SELECT fdc_id FROM rerank_cache WHERE search_query = ?", (search_query,))
        row = cur.fetchone()
        con.close()
        
        if row is None:
            return False, None
            
        fdc_id = row[0]
        return True, (None if fdc_id == -1 else fdc_id)
    except Exception:
        return False, None

def set_cached_id(search_query: str, fdc_id: int | None):
    """Saves the result to cache. Saves -1 if fdc_id is None."""
    save_id = -1 if fdc_id is None else fdc_id
    try:
        con = sqlite3.connect(CACHE_DB)
        con.execute(
            "INSERT OR REPLACE INTO rerank_cache (search_query, fdc_id) VALUES (?, ?)",
            (search_query, save_id)
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[CACHE ERROR] Could not save to cache: {e}")