import sqlite3
from datetime import datetime

LOG_DB = "logs.db"

def init_log_db():
    con = sqlite3.connect(LOG_DB)
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS request_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            endpoint TEXT,
            user_note TEXT,
            status TEXT,
            error_message TEXT,
            processing_time REAL,
            model_used TEXT  -- YENI SUTUN EKLENDI
        )
    """)
    con.commit()
    con.close()

def log_request(endpoint: str, user_note: str, status: str, error_message: str = "", processing_time: float = 0.0, model_used: str = "unknown"):
    try:
        con = sqlite3.connect(LOG_DB)
        cur = con.cursor()
        cur.execute(
            "INSERT INTO request_logs (timestamp, endpoint, user_note, status, error_message, processing_time, model_used) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now().isoformat(), endpoint, user_note, status, error_message, processing_time, model_used)
        )
        con.commit()
        con.close()
    except Exception as e:
        print(f"[CRITICAL LOG ERROR] Log veritabani hatasi: {e}")