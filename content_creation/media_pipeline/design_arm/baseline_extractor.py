import cv2
import numpy as np
import sqlite3
import os
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'design_telemetry.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS asset_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_file TEXT,
            width INTEGER,
            height INTEGER,
            overexposure_percent REAL,
            timestamp DATETIME
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS generation_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            baseline_id INTEGER,
            generated_file TEXT,
            final_prompt TEXT,
            new_overexposure_percent REAL,
            delta_overexposure REAL,
            is_flagged_bad BOOLEAN,
            timestamp DATETIME
        )
    ''')
    conn.commit()
    conn.close()

def calculate_overexposure(image_path, threshold=250):
    """Calculates percentage of pixels near maximum intensity."""
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Could not read image at {image_path}")
    
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)
    
    overexposed_pixels = np.count_nonzero(thresh)
    total_pixels = gray.size
    percentage = (overexposed_pixels / total_pixels) * 100
    return percentage

def register_baseline(image_path):
    """Extracts baseline metrics and logs to SQLite."""
    img = cv2.imread(image_path)
    h, w, _ = img.shape
    overexp = calculate_overexposure(image_path)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO asset_baselines (original_file, width, height, overexposure_percent, timestamp) VALUES (?, ?, ?, ?, ?)",
        (image_path, w, h, overexp, datetime.utcnow().isoformat())
    )
    baseline_id = c.lastrowid
    conn.commit()
    conn.close()
    
    return baseline_id, overexp

def log_generation(baseline_id, generated_file, final_prompt, baseline_overexp):
    """Compares the new generation against the baseline."""
    new_overexp = calculate_overexposure(generated_file)
    delta = new_overexp - baseline_overexp
    
    # Flag as bad if AI drastically blew out the lighting (e.g., > 5% increase)
    is_flagged_bad = delta > 5.0 
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO generation_logs (baseline_id, generated_file, final_prompt, new_overexposure_percent, delta_overexposure, is_flagged_bad, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (baseline_id, generated_file, final_prompt, new_overexp, delta, is_flagged_bad, datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()
    
    return is_flagged_bad, delta

if __name__ == "__main__":
    init_db()
    print("Baseline DB initialized.")
