import asyncio
import json
import sqlite3
import pandas as pd
from datetime import datetime
import websockets
import os
from dotenv import load_dotenv
from thefuzz import process

load_dotenv()

# Initialize SQLite database
DB_PATH = "portfolio.db"
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player TEXT,
            year TEXT,
            set_name TEXT,
            variation TEXT,
            number TEXT,
            category TEXT,
            condition TEXT,
            estimated_value REAL,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

def fuzzy_match_category(raw_category):
    valid_categories = ["Baseball", "Basketball", "Football", "Hockey", "Soccer", "Pokemon", "Magic", "F1", "UFC", "Wrestling"]
    match, score = process.extractOne(raw_category, valid_categories)
    return match if score > 80 else "Other"

async def handler(websocket):
    async for message in websocket:
        try:
            data = json.loads(message)
            action = data.get("action")

            if action == "get_checklist":
                # Mock checklist payload for 2018/2019 Baseball
                checklist = [
                    {"id": 1, "player": "Ronald Acuna Jr.", "year": "2019", "set_name": "Topps Chrome", "number": "001", "category": "Basebal"},
                    {"id": 2, "player": "Shohei Ohtani", "year": "2018", "set_name": "Topps Chrome Update", "number": "HMT1", "category": "Baseball"},
                    {"id": 3, "player": "Mike Trout", "year": "2011", "set_name": "Topps Update", "number": "US175", "category": "Bsbll"}
                ]
                await websocket.send(json.dumps({"type": "checklist", "data": checklist}))

            elif action == "evaluate_cards":
                cards = data.get("cards", [])
                # Mock valuation using an arbitrary rule
                valuations = []
                for c in cards:
                    if "Trout" in c["player"]:
                        c["estimated_value"] = 500.00
                    elif "Ohtani" in c["player"]:
                        c["estimated_value"] = 250.00
                    else:
                        c["estimated_value"] = 25.00
                        
                    c["condition"] = "Raw"
                    valuations.append(c)
                await websocket.send(json.dumps({"type": "valuations", "data": valuations}))

            elif action == "export_csv":
                cards = data.get("cards", [])
                
                # 1. Log to SQLite
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                for c in cards:
                    cursor.execute("""
                        INSERT INTO inventory (player, year, set_name, variation, number, category, condition, estimated_value, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (c.get("player"), c.get("year"), c.get("set_name"), c.get("variation", ""), c.get("number"), c.get("category"), c.get("condition"), c.get("estimated_value"), now))
                conn.commit()
                conn.close()

                # 2. Pandas ETL for Card Ladder
                rows = []
                today = datetime.now().strftime("%m/%d/%Y")
                for c in cards:
                    rows.append({
                        "Date Purchased": today,
                        "Quantity": 1,
                        "Player": c.get("player", ""),
                        "Year": c.get("year", ""),
                        "Set": c.get("set_name", ""),
                        "Variation": c.get("variation", ""),
                        "Number": c.get("number", ""),
                        "Category": fuzzy_match_category(c.get("category", "")),
                        "Condition": c.get("condition", "Raw"),
                        "Investment": 0.0,
                        "Estimated Value": c.get("estimated_value", 0.0),
                        "Ladder ID": "",
                        "Notes": "Auto-ingested",
                        "Date Sold": "",
                        "Sold Price": "",
                        "Image": ""
                    })
                
                df = pd.DataFrame(rows)
                csv_path = "card_ladder_upload_ready.csv"
                df.to_csv(csv_path, index=False)
                
                await websocket.send(json.dumps({"type": "export_success", "path": csv_path}))
                
        except Exception as e:
            await websocket.send(json.dumps({"type": "error", "message": str(e)}))

async def main():
    port = 9000
    while port < 9010:
        try:
            print(f"Starting server on port {port}...")
            async with websockets.serve(handler, "localhost", port):
                await asyncio.Future()  # run forever
            break
        except OSError as e:
            if getattr(e, 'winerror', None) == 10048 or e.errno == 10048 or "10048" in str(e):
                print(f"Port {port} in use, trying next...")
                port += 1
            else:
                raise

if __name__ == "__main__":
    asyncio.run(main())
