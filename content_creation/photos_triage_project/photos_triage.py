import os
import shutil
import sqlite3
import json
from pathlib import Path

def setup_db(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS media (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT,
            album TEXT,
            timestamp TEXT,
            original_path TEXT,
            new_path TEXT,
            ai_tags TEXT,
            artists TEXT
        )
    ''')
    conn.commit()
    return conn

def process_takeout(takeout_dir, output_dir, db_path):
    conn = setup_db(db_path)
    cursor = conn.cursor()
    
    photos_dir = os.path.join(takeout_dir, "Google Photos")
    if not os.path.exists(photos_dir):
        return

    for album_name in os.listdir(photos_dir):
        album_path = os.path.join(photos_dir, album_name)
        if not os.path.isdir(album_path):
            continue
            
        for file in os.listdir(album_path):
            # Only process actual media files, skip json sidecars initially
            if file.endswith('.json'):
                continue
                
            media_path = os.path.join(album_path, file)
            json_path = media_path + '.json'
            
            timestamp = None
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                        timestamp = meta.get('photoTakenTime', {}).get('timestamp')
                except Exception:
                    pass
            
            # Destination path
            dest_album_dir = os.path.join(output_dir, album_name)
            os.makedirs(dest_album_dir, exist_ok=True)
            dest_media_path = os.path.join(dest_album_dir, file)
            
            # Bit-for-bit copy (Lossless)
            shutil.copy2(media_path, dest_media_path)
            
            # Insert into SQLite
            cursor.execute('''
                INSERT INTO media (filename, album, timestamp, original_path, new_path)
                VALUES (?, ?, ?, ?, ?)
            ''', (file, album_name, timestamp, media_path, dest_media_path))
            
    conn.commit()
    conn.close()

if __name__ == "__main__":
    pass
