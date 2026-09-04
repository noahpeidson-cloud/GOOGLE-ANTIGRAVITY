import uvicorn
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from typing import List

app = FastAPI(title="Antigravity Omnichannel Ingestion Gateway")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"[*] Chrome Extension Connected. Active peers: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"[*] Chrome Extension Disconnected.")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_text(json.dumps(message))

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            # Ingest DOM payloads and telemetry from the Chrome Extension
            data = await websocket.receive_text()
            print(f"[DOM_INGEST] Received payload stream: {data[:150]}...", flush=True)
            
            # Write to disk for immediate agent inspection
            with open("last_payload.json", "w", encoding="utf-8") as f:
                f.write(data)
            
            # FUTURE HOOK: Pipe 'data' into the local Spark Structured Streaming pipeline
            # enforcing the V1_OMNICHANNEL_ARCHITECTURE_SPEC.md requirements.
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    print("Starting Antigravity WebSocket Gateway on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002)
