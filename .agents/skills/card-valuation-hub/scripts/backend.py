import asyncio
import json
import sqlite3
import pandas as pd
from datetime import datetime
import websockets
import os
import urllib.parse
from thefuzz import process

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
                # Mock checklist payload. In production, this would be populated by the MCP browser scrape.
                checklist = [
                    {"id": 1, "player": "Ronald Acuna Jr.", "year": "2019", "set_name": "Topps Chrome", "number": "001", "category": "Basebal"},
                    {"id": 2, "player": "Shohei Ohtani", "year": "2018", "set_name": "Topps Chrome Update", "number": "HMT1", "category": "Baseball"},
                    {"id": 3, "player": "Mike Trout", "year": "2011", "set_name": "Topps Update", "number": "US175", "category": "Bsbll"}
                ]
                
                # Pre-generate eBay Sold search URLs for manual workflow
                for c in checklist:
                    query = f"{c['year']} {c['set_name']} {c['player']} {c['number']}"
                    safe_query = urllib.parse.quote_plus(query)
                    c["ebay_link"] = f"https://www.ebay.com/sch/i.html?_nkw={safe_query}&LH_Sold=1&LH_Complete=1"

                await websocket.send(json.dumps({"type": "checklist", "data": checklist}))

            elif action == "export_csv":
                cards = data.get("cards", [])
                
                # 1. Log to SQLite
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                for c in cards:
                    # The UI now passes the user-entered estimated_value
                    val = float(c.get("estimated_value", 0.0))
                    
                    cursor.execute("""
                        INSERT INTO inventory (player, year, set_name, variation, number, category, condition, estimated_value, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (c.get("player"), c.get("year"), c.get("set_name"), c.get("variation", ""), c.get("number"), c.get("category"), c.get("condition", "Raw"), val, now))
                conn.commit()
                conn.close()

                # 2. Pandas ETL for Card Ladder
                rows = []
                today = datetime.now().strftime("%m/%d/%Y")
                for c in cards:
                    val = float(c.get("estimated_value", 0.0))
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
                        "Estimated Value": val,
                        "Ladder ID": "",
                        "Notes": "Manual Hub Valuation",
                        "Date Sold": "",
                        "Sold Price": "",
                        "Image": ""
                    })
                
                df = pd.DataFrame(rows)
                csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "sports_cards", "card_ladder_upload_ready.csv")
                df.to_csv(csv_path, index=False)
                
                await websocket.send(json.dumps({"type": "export_success", "path": os.path.abspath(csv_path)}))
            elif action == "bookmarklet_extract":
                title = data.get("title", "")
                url = data.get("url", "")
                
                # Naive parsing of Card Ladder Title (e.g. "2019 Topps Chrome Ronald Acuna Jr. #001 - Card Ladder")
                import re
                year = ""
                year_match = re.search(r'\b(19\d{2}|20\d{2})\b', title)
                if year_match:
                    year = year_match.group(1)
                    
                number = ""
                num_match = re.search(r'#(\w+)', title)
                if num_match:
                    number = num_match.group(1)
                    
                title_clean = title.replace(" - Card Ladder", "").replace(" | Card Ladder", "")
                
                # Log to SQLite
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO inventory (player, year, set_name, variation, number, category, condition, estimated_value, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (title_clean, year, "Unknown Set", "", number, "Other", "Raw", 0.0, now))
                conn.commit()
                conn.close()

                # Re-export entire DB to CSV to ensure it's updated
                conn = sqlite3.connect(DB_PATH)
                df_db = pd.read_sql_query("SELECT * FROM inventory", conn)
                conn.close()
                
                rows = []
                today = datetime.now().strftime("%m/%d/%Y")
                for _, row in df_db.iterrows():
                    rows.append({
                        "Date Purchased": today,
                        "Quantity": 1,
                        "Player": row["player"],
                        "Year": row["year"],
                        "Set": row["set_name"],
                        "Variation": row["variation"],
                        "Number": row["number"],
                        "Category": row["category"],
                        "Condition": row["condition"],
                        "Investment": 0.0,
                        "Estimated Value": row["estimated_value"],
                        "Ladder ID": url, # Save the URL here for reference
                        "Notes": "Auto-ingested via Bookmarklet",
                        "Date Sold": "",
                        "Sold Price": "",
                        "Image": ""
                    })
                
                df_csv = pd.DataFrame(rows)
                csv_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "sports_cards", "card_ladder_upload_ready.csv")
                df_csv.to_csv(csv_path, index=False)
                
                await websocket.send(json.dumps({"type": "export_success", "path": os.path.abspath(csv_path)}))
                
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
