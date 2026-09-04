import sqlite3
import datetime
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DB_PATH = os.path.join(os.path.dirname(__file__), "trends.db")

def init_db():
    """Initializes the SQLite database with the required schemas."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for storing daily viral trends
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS viral_trends (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL,
        trend_name TEXT NOT NULL,
        tags TEXT,
        date_added DATE NOT NULL
    )
    """)
    
    # Table for storing video grading telemetry
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_grades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        video_filename TEXT NOT NULL,
        viral_potential_score INTEGER,
        feedback_notes TEXT,
        date_graded DATE NOT NULL,
        status TEXT DEFAULT 'PENDING_APPROVAL'
    )
    """)
    
    conn.commit()
    conn.close()
    logging.info(f"Database initialized at {DB_PATH}")

def garbage_collect_trends(days_to_keep=14):
    """
    Generational Mark-and-Sweep GC.
    Deletes trends older than the specified number of days to prevent context bloat.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cutoff_date = (datetime.datetime.now() - datetime.timedelta(days=days_to_keep)).strftime('%Y-%m-%d')
    
    cursor.execute("DELETE FROM viral_trends WHERE date_added < ?", (cutoff_date,))
    deleted_count = cursor.rowcount
    
    conn.commit()
    conn.close()
    
    logging.info(f"Garbage Collection complete: Swept {deleted_count} outdated trends older than {days_to_keep} days.")

if __name__ == "__main__":
    init_db()
    garbage_collect_trends()
