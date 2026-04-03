import sqlite3
from pathlib import Path

DB_PATH = Path("food.db")

def get_connection() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con
