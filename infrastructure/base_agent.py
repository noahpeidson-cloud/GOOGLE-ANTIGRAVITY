"""
Universal Base Antigravity Agent & ML Telemetry Infrastructure (base_agent.py).
Extracts @hooks.post_turn telemetry into a reusable hook factory and agent wrapper
with robust SQLite WAL-mode thread and process concurrency.
Strict compliance with Antigravity IDE Component Unification (Milestone M3).
"""

import os
import sys
import json
import time
import sqlite3
import logging
import traceback
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Union

from dotenv import load_dotenv
load_dotenv()

from google.antigravity import LocalAgentConfig, Agent, types
from google.antigravity.hooks import hooks

logger = logging.getLogger("base_agent")

_DEFAULT_TELEMETRY_DB = r"G:\My Drive\GOOGLE ANTIGRAVITY\health_telemetry.db"
DEFAULT_TELEMETRY_DB = os.getenv("AGENT_TELEMETRY_DB", _DEFAULT_TELEMETRY_DB)


def init_telemetry_db(
    db_path: str = DEFAULT_TELEMETRY_DB,
    table_name: str = "agent_telemetry"
) -> None:
    """
    Initializes SQLite telemetry database enforcing WAL mode and concurrency pragmas.
    """
    db_dir = os.path.dirname(os.path.abspath(db_path))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    with sqlite3.connect(db_path, timeout=10.0) as conn:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        
        # Primary structured agent telemetry table
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp_iso TEXT NOT NULL,
                timestamp_ms INTEGER NOT NULL,
                agent_name TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                details TEXT,
                metadata_json TEXT DEFAULT '{{}}'
            )
        """)
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_name_ts 
            ON {table_name}(agent_name, timestamp_ms DESC)
        """)
        conn.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{table_name}_status 
            ON {table_name}(status)
        """)

        # Ensure compatibility with legacy deployment_logs schema if requested
        conn.execute("""
            CREATE TABLE IF NOT EXISTS deployment_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT,
                details TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


def record_agent_telemetry(
    agent_name: str,
    event_type: str,
    status: str,
    details: str,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: str = DEFAULT_TELEMETRY_DB,
    table_name: str = "agent_telemetry",
) -> int:
    """
    Thread-safe and multi-process safe insertion into SQLite telemetry store with WAL mode.
    Returns the inserted record ID.
    """
    try:
        init_telemetry_db(db_path=db_path, table_name=table_name)
        now = datetime.now(timezone.utc)
        ts_iso = now.isoformat()
        ts_ms = int(now.timestamp() * 1000)
        meta_json = json.dumps(metadata or {})

        with sqlite3.connect(db_path, timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            cur = conn.cursor()
            cur.execute(
                f"""
                INSERT INTO {table_name}
                (timestamp_iso, timestamp_ms, agent_name, event_type, status, details, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ts_iso, ts_ms, agent_name, event_type, status, str(details), meta_json)
            )
            inserted_id = cur.lastrowid or 0
            
            # If writing to booth_telemetry or deployment_logs table, mirror record
            if "booth" in db_path or table_name == "deployment_logs":
                try:
                    cur.execute(
                        "INSERT INTO deployment_logs (status, details) VALUES (?, ?)",
                        (status, str(details))
                    )
                except Exception:
                    pass

            conn.commit()
            logger.info(f"[TELEMETRY:{agent_name}] {event_type} - {status} (ID: {inserted_id})")
            return inserted_id
    except Exception as e:
        logger.error(f"[TELEMETRY:{agent_name}] Failed to persist telemetry: {e}")
        return -1


def create_telemetry_post_turn_hook(
    agent_name: str,
    db_path: str = DEFAULT_TELEMETRY_DB,
    table_name: str = "agent_telemetry",
    success_keyword: Optional[str] = None
) -> Callable:
    """
    Parameterized hook factory generating an @hooks.post_turn telemetry callback.
    """
    @hooks.post_turn
    async def post_turn_telemetry(data: Any) -> None:
        try:
            text_payload = str(data)
            if success_keyword:
                status = "SUCCESS" if success_keyword in text_payload else "EVALUATE"
            else:
                if "error" in text_payload.lower() or "exception" in text_payload.lower():
                    status = "ERROR"
                else:
                    status = "SUCCESS"

            record_agent_telemetry(
                agent_name=agent_name,
                event_type="POST_TURN",
                status=status,
                details=text_payload,
                metadata={"payload_length": len(text_payload), "timestamp": time.time()},
                db_path=db_path,
                table_name=table_name,
            )
        except Exception as err:
            logger.error(f"[HOOK_ERROR:{agent_name}] Error executing post_turn telemetry: {err}")

    return post_turn_telemetry


def create_telemetry_error_hook(
    agent_name: str,
    db_path: str = DEFAULT_TELEMETRY_DB,
    table_name: str = "agent_telemetry"
) -> Callable:
    """
    Parameterized hook factory generating an @hooks.on_tool_error telemetry callback.
    """
    @hooks.on_tool_error
    async def error_telemetry(error: Exception) -> Optional[str]:
        try:
            record_agent_telemetry(
                agent_name=agent_name,
                event_type="TOOL_ERROR",
                status="ERROR",
                details=str(error),
                metadata={
                    "exception_type": type(error).__name__,
                    "traceback": traceback.format_exc()
                },
                db_path=db_path,
                table_name=table_name,
            )
        except Exception as err:
            logger.error(f"[HOOK_ERROR:{agent_name}] Error executing on_tool_error telemetry: {err}")
        return None

    return error_telemetry


class BaseAntigravityAgent:
    """
    Universal Base Antigravity Agent wrapper.
    Encapsulates agent configuration, telemetry lifecycle hooks, WAL-mode SQLite
    persistence, and resilient turn execution.
    """

    def __init__(
        self,
        name: str,
        system_instructions: str,
        tools: Optional[List[Any]] = None,
        model: str = "gemini-3.7-flash",
        telemetry_db_path: str = DEFAULT_TELEMETRY_DB,
        telemetry_table: str = "agent_telemetry",
        success_keyword: Optional[str] = None,
        extra_hooks: Optional[List[Any]] = None,
        retry_config: Optional[Any] = None,
        enable_telemetry: bool = True,
    ) -> None:
        self.name = name
        self.system_instructions = system_instructions
        self.tools = tools or []
        self.model = model
        self.telemetry_db_path = telemetry_db_path
        self.telemetry_table = telemetry_table
        self.success_keyword = success_keyword
        self.enable_telemetry = enable_telemetry

        init_telemetry_db(self.telemetry_db_path, self.telemetry_table)

        self.hooks: List[Any] = []
        if self.enable_telemetry:
            self.post_turn_hook = create_telemetry_post_turn_hook(
                agent_name=self.name,
                db_path=self.telemetry_db_path,
                table_name=self.telemetry_table,
                success_keyword=self.success_keyword
            )
            self.error_hook = create_telemetry_error_hook(
                agent_name=self.name,
                db_path=self.telemetry_db_path,
                table_name=self.telemetry_table
            )
            self.hooks.extend([self.post_turn_hook, self.error_hook])

        if extra_hooks:
            self.hooks.extend(extra_hooks)

        self.retry_config = retry_config or types.RetryConfig.benchmark()

        self.config = LocalAgentConfig(
            model=self.model,
            system_instructions=self.system_instructions,
            tools=self.tools,
            hooks=self.hooks,
            retry_config=self.retry_config
        )

    def get_config(self) -> LocalAgentConfig:
        """Returns the configured LocalAgentConfig instance."""
        return self.config

    def record_telemetry(
        self,
        event_type: str,
        status: str,
        details: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Records a custom telemetry event for this agent instance."""
        return record_agent_telemetry(
            agent_name=self.name,
            event_type=event_type,
            status=status,
            details=details,
            metadata=metadata,
            db_path=self.telemetry_db_path,
            table_name=self.telemetry_table,
        )

    async def execute_turn(self, prompt: str) -> str:
        """
        Executes a prompt turn through the agent with automatic telemetry capture.
        """
        try:
            async with Agent(self.config) as agent:
                response = await agent.chat(prompt)
                res_text = await response.text()
                return res_text
        except Exception as e:
            logger.warning(f"[AGENT:{self.name}] Agent turn execution exception: {e}")
            self.record_telemetry(
                event_type="TURN_EXECUTION_EXCEPTION",
                status="ERROR",
                details=str(e),
                metadata={"prompt": prompt, "traceback": traceback.format_exc()}
            )
            raise e

    async def chat(self, prompt: str) -> str:
        """Alias for execute_turn."""
        return await self.execute_turn(prompt)
