"""
Unified Ops Hub - Headless Backend Server
FastAPI server featuring:
- GET / and GET /status returning {"status": "online"}
- WebSocket event bus for real-time system telemetry
- Decoupled REST endpoints for Vector Hub and Ingest Daemon
"""

import asyncio
import datetime
import json
import logging
import random
from contextlib import asynccontextmanager
from typing import Dict, Any, Set, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("unified_ops_hub.backend")

class EventBus:
    """Manages active WebSocket connections and broadcasts telemetry events."""

    def __init__(self) -> None:
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.active_connections:
            return
        payload = json.dumps(message)
        dead_connections = set()
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(payload)
                except Exception as e:
                    logger.warning(f"Failed to send to client, scheduling removal: {e}")
                    dead_connections.add(connection)
            for dead in dead_connections:
                self.active_connections.discard(dead)

bus = EventBus()

# Initial state for telemetry
telemetry_state: Dict[str, Any] = {
    "ingest_daemon": {
        "status": "idle",
        "last_sync": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "queued_items": 0,
        "processed_count": 1420,
        "health": "healthy"
    },
    "vector_hub": {
        "status": "indexed",
        "total_vectors": 85420,
        "dimension": 1536,
        "avg_query_latency_ms": 11.4,
        "index_integrity": 1.0
    },
    "system": {
        "cpu_usage_pct": 14.2,
        "memory_usage_mb": 428.6,
        "uptime_seconds": 3600
    }
}

async def telemetry_background_task():
    """Simulate and publish periodic telemetry events across the WebSocket bus."""
    ticks = 0
    daemon_states = ["idle", "processing", "indexing", "syncing"]
    while True:
        try:
            await asyncio.sleep(2.0)
            ticks += 1
            # Update telemetry state dynamically
            telemetry_state["system"]["cpu_usage_pct"] = round(12.0 + random.uniform(-4.0, 18.0), 1)
            telemetry_state["system"]["memory_usage_mb"] = round(420.0 + random.uniform(0.0, 30.0), 1)
            telemetry_state["system"]["uptime_seconds"] += 2
            
            if ticks % 5 == 0:
                telemetry_state["ingest_daemon"]["status"] = random.choice(daemon_states)
                telemetry_state["ingest_daemon"]["last_sync"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                telemetry_state["ingest_daemon"]["queued_items"] = random.randint(0, 5)
                telemetry_state["ingest_daemon"]["processed_count"] += random.randint(0, 3)

            telemetry_state["vector_hub"]["avg_query_latency_ms"] = round(9.0 + random.uniform(0.5, 6.0), 2)
            
            telemetry_event = {
                "event": "telemetry_update",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "data": telemetry_state,
                "connected_clients": len(bus.active_connections)
            }
            await bus.broadcast(telemetry_event)
        except asyncio.CancelledError:
            logger.info("Telemetry background worker cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in telemetry loop: {e}", exc_info=True)
            await asyncio.sleep(1.0)

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = asyncio.create_task(telemetry_background_task())
    logger.info("Unified Ops Hub headless backend initialized.")
    yield
    worker.cancel()
    try:
        await worker
    except asyncio.CancelledError:
        pass
    logger.info("Unified Ops Hub headless backend shut down.")

app = FastAPI(
    title="Unified Ops Hub Backend",
    description="Headless telemetry and event bus API for Unified Ops Hub",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TelemetryEventPayload(BaseModel):
    event: str = Field(..., description="Event name/type")
    data: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary event payload")

@app.get("/")
async def root_status():
    """Primary health check endpoint returning { 'status': 'online' }."""
    return {"status": "online"}

@app.get("/status")
async def get_status():
    """Alternative status endpoint returning { 'status': 'online' }."""
    return {"status": "online"}

@app.get("/health")
async def get_health():
    """Health endpoint returning { 'status': 'online' }."""
    return {"status": "online"}

@app.get("/api/telemetry")
async def get_telemetry_snapshot():
    """Get current snapshot of telemetry state."""
    return {
        "status": "online",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "telemetry": telemetry_state,
        "connected_clients": len(bus.active_connections)
    }

@app.get("/api/vector-hub/search")
async def vector_hub_search_placeholder(q: Optional[str] = Query(None, description="Query string"), limit: int = 10):
    """Placeholder endpoint for Vector Hub semantic search results."""
    query_term = q.strip() if q else "system_init"
    mock_dataset = [
        {
            "id": "vec-0101",
            "title": "Ingestion Protocol Specification v2.4",
            "snippet": f"Specifies chunking policy and cosine distance indexing for '{query_term}'. High overlap score with knowledge base index.",
            "score": 0.962,
            "collection": "protocols",
            "indexed_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=5)).isoformat()
        },
        {
            "id": "vec-0102",
            "title": "Ops Hub Telemetry Schema & Transport",
            "snippet": f"WebSocket multiplexing for node health, memory pressure metrics, and query latency relating to '{query_term}'.",
            "score": 0.915,
            "collection": "architecture",
            "indexed_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=24)).isoformat()
        },
        {
            "id": "vec-0103",
            "title": "Media Studio Faststart 720p Proxy Pipeline",
            "snippet": f"FFmpeg sub-second trimming and dynamic audio waveform peak detection algorithm for '{query_term}'.",
            "score": 0.884,
            "collection": "media",
            "indexed_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)).isoformat()
        },
        {
            "id": "vec-0104",
            "title": "Antigravity Daemon Failover and Sync Watcher",
            "snippet": f"Ingestion daemon background polling loop, heartbeat watcher, and crash recovery routines for '{query_term}'.",
            "score": 0.829,
            "collection": "infrastructure",
            "indexed_at": (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=6)).isoformat()
        }
    ]
    return {
        "query": q or "",
        "total_matches": len(mock_dataset),
        "results": mock_dataset[:limit]
    }

@app.get("/api/ingest/status")
async def ingest_daemon_status():
    """Placeholder endpoint for Ingest Daemon state."""
    return {
        "daemon": telemetry_state["ingest_daemon"],
        "system_load": telemetry_state["system"],
        "status": "online"
    }

@app.post("/api/events")
async def publish_event(payload: TelemetryEventPayload):
    """Publish custom event onto the WebSocket bus."""
    event_dict = {
        "event": payload.event,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "data": payload.data
    }
    await bus.broadcast(event_dict)
    return {"status": "published", "event": payload.event}

@app.websocket("/ws")
@app.websocket("/ws/telemetry")
async def websocket_telemetry_bus(websocket: WebSocket):
    """WebSocket event bus for live telemetry streaming."""
    await bus.connect(websocket)
    try:
        # Send initial telemetry snapshot on connection
        await websocket.send_text(json.dumps({
            "event": "connected",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "data": telemetry_state
        }))
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
                action = msg.get("action") or msg.get("type")
                if action == "ping":
                    await websocket.send_text(json.dumps({
                        "event": "pong",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
                    }))
                elif action == "broadcast":
                    # Re-broadcast to all clients
                    await bus.broadcast({
                        "event": msg.get("event", "client_broadcast"),
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "data": msg.get("data", {})
                    })
                elif action == "trigger_sync":
                    telemetry_state["ingest_daemon"]["status"] = "indexing"
                    telemetry_state["ingest_daemon"]["queued_items"] = random.randint(3, 8)
                    await bus.broadcast({
                        "event": "ingest_sync_triggered",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "data": telemetry_state
                    })
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "invalid_json"}))
    except WebSocketDisconnect:
        await bus.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket client error: {e}")
        await bus.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
