import os
import json
import sqlite3
import urllib.request
import urllib.error
import glob
from typing import List, Dict, Any

DB_PATH = r"D:\AI_Platform\telemetry\vector_memory\vector_memory.db"
BRAIN_DIR = r"D:\AI_Platform\.gemini\antigravity\brain"
OLLAMA_API_URL = "http://localhost:11434/api/embeddings"
EMBED_MODEL = "nomic-embed-text"

def get_embedding(text: str) -> List[float]:
    data = json.dumps({
        "model": EMBED_MODEL,
        "prompt": text
    }).encode("utf-8")
    
    req = urllib.request.Request(OLLAMA_API_URL, data=data, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            result = json.loads(response.read().decode("utf-8"))
            if "embedding" not in result:
                raise RuntimeError(
                    f"CRITICAL (R1 Violation Prevention): Ollama at {OLLAMA_API_URL} responded "
                    f"200 OK but the body has no 'embedding' key (schema mismatch, wrong service "
                    f"on that port, or a server-side error reported as 200). Mock embeddings are "
                    f"strictly forbidden -- falling back to an empty vector here would silently "
                    f"write a degenerate row that ingestion's dedup check then skips forever.\n"
                    f"Response keys: {list(result.keys())}"
                )
            return result["embedding"]
    except urllib.error.URLError as e:
        raise RuntimeError(
            f"CRITICAL (R1 Violation Prevention): Failed to connect to local Ollama at {OLLAMA_API_URL}. "
            f"Mock embeddings are strictly forbidden. Ensure the Ollama engine is running before executing ingestion.\n"
            f"Details: {e}"
        ) from e

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS memory_turns (
            id TEXT PRIMARY KEY,
            conversation_id TEXT,
            turn_index INTEGER,
            user_prompt TEXT,
            model_response TEXT,
            embedding JSON
        )
    ''')
    conn.commit()
    return conn

def parse_transcript(filepath: str) -> List[Dict[str, Any]]:
    turns = []
    current_user_prompt = None
    current_model_response = []
    turn_index = 0
    
    # Path is like: D:\AI_Platform\.gemini\antigravity\brain\<conv_id>\.system_generated\logs\transcript.jsonl
    conversation_id = filepath.split(os.sep)[-4]
    
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            try:
                step = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            step_type = step.get("type")
            content = step.get("content", "")
            
            if step_type == "USER_INPUT":
                if current_user_prompt is not None:
                    turns.append({
                        "id": f"{conversation_id}_{turn_index}",
                        "conversation_id": conversation_id,
                        "turn_index": turn_index,
                        "user_prompt": current_user_prompt,
                        "model_response": "\n".join(current_model_response).strip()
                    })
                    turn_index += 1
                
                current_user_prompt = content
                current_model_response = []
                
            elif step_type == "PLANNER_RESPONSE" and content:
                if current_user_prompt is not None:
                    current_model_response.append(content)
                    
        # Add the final turn if any
        if current_user_prompt is not None:
            turns.append({
                "id": f"{conversation_id}_{turn_index}",
                "conversation_id": conversation_id,
                "turn_index": turn_index,
                "user_prompt": current_user_prompt,
                "model_response": "\n".join(current_model_response).strip()
            })
            
    return turns

def ingest_transcripts(sample_size: int = None):
    conn = init_db()
    cursor = conn.cursor()
    
    search_pattern = os.path.join(BRAIN_DIR, "*", ".system_generated", "logs", "transcript.jsonl")
    transcript_files = glob.glob(search_pattern)
    
    if sample_size is not None:
        transcript_files = transcript_files[:sample_size]
        
    for filepath in transcript_files:
        print(f"Processing {filepath}...")
        turns = parse_transcript(filepath)
        for turn in turns:
            cursor.execute("SELECT id FROM memory_turns WHERE id = ?", (turn["id"],))
            if cursor.fetchone():
                continue
                
            text_to_embed = f"User: {turn['user_prompt']}\nModel: {turn['model_response']}"
            embedding = get_embedding(text_to_embed)
            
            cursor.execute('''
                INSERT INTO memory_turns (id, conversation_id, turn_index, user_prompt, model_response, embedding)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                turn["id"],
                turn["conversation_id"],
                turn["turn_index"],
                turn["user_prompt"],
                turn["model_response"],
                json.dumps(embedding)
            ))
        conn.commit()
        
    conn.close()
    print(f"Ingestion complete. Processed {len(transcript_files)} files.")

if __name__ == "__main__":
    print("Starting vector memory hub ingestion (sample of 2 files)...")
    ingest_transcripts(sample_size=2)
