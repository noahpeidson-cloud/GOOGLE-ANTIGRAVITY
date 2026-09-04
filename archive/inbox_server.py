import sqlite3
import json
from datetime import datetime
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os

app = FastAPI(title="Zero Friction Capture Inbox")

# Allow Chrome Extension to POST
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict to extension ID
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_PATH = os.path.join(os.path.dirname(__file__), "inbox.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_url TEXT,
            timestamp TEXT,
            extracted_data_json TEXT,
            processed BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

init_db()

class IngestPayload(BaseModel):
    source_url: str
    timestamp: str
    extracted_data: Dict[str, Any]

@app.post("/ingest")
async def ingest_data(payload: IngestPayload):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO inbox (source_url, timestamp, extracted_data_json)
            VALUES (?, ?, ?)
        ''', (payload.source_url, payload.timestamp, json.dumps(payload.extracted_data)))
        conn.commit()
        conn.close()
        return {"status": "success", "message": "Data ingested into local SQLite inbox."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print(f"Starting Zero Friction Capture Inbox Server on port 8080...")
    print(f"Database path: {DB_PATH}")
    uvicorn.run(app, host="127.0.0.1", port=8080)
