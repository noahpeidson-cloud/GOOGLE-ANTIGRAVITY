"""
database_sink.py - PostgreSQL Data Sink for Quick Share AI Loop
Connects to Google Cloud SQL PostgreSQL / Firebase Data Connect via psycopg2 ThreadedConnectionPool.
Implements Rule R26 (Fail-Fast Auth), automatic connection recovery, context manager, and JSONB adaptation.
"""

import os
import json
import logging
import atexit
from pathlib import Path
from typing import Union, Dict, Any, Optional, Generator
from contextlib import contextmanager
from dotenv import load_dotenv
import psycopg2
from psycopg2 import pool, extras
from psycopg2.extras import Json

# Configure module logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Rule R26: Explicitly load local .env file
ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

REQUIRED_ENV_VARS = ["PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DB"]

# Global singleton connection pool
_CONNECTION_POOL: Optional[pool.ThreadedConnectionPool] = None


def get_db_config() -> Dict[str, Any]:
    """
    Loads and validates PostgreSQL configuration from environment variables.
    Adheres strictly to Rule R26 (The Background Daemon Auth Guardrail).
    Fails fast with a loud ValueError if any required environment variable is missing or empty.
    """
    # Reload .env in case environment was mutated or initialized dynamically
    load_dotenv(dotenv_path=ENV_PATH, override=False)
    
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var) or not os.getenv(var).strip()]
    if missing:
        error_msg = (
            f"FATAL: Missing required PostgreSQL environment variables in .env: {missing}. "
            f"Adhering to Workspace Rule R26 (The Background Daemon Auth Guardrail), "
            f"the pipeline is halted immediately to prevent silent data loss."
        )
        logger.error(error_msg)
        raise ValueError(error_msg)
    
    # Port parsing & validation
    raw_port = os.getenv("PG_PORT", "5432")
    if raw_port is None or not str(raw_port).strip():
        port = 5432
    else:
        try:
            port = int(str(raw_port).strip())
        except ValueError:
            raise ValueError(f"Invalid PG_PORT value '{raw_port}': must be an integer.")

    # Pool & timeout settings
    try:
        minconn = int(os.getenv("PG_MIN_CONN", "1").strip())
        maxconn = int(os.getenv("PG_MAX_CONN", "10").strip())
        connect_timeout = int(os.getenv("PG_CONNECT_TIMEOUT", "10").strip())
    except ValueError as e:
        raise ValueError(f"Invalid pool/timeout configuration: {e}")

    return {
        "host": os.getenv("PG_HOST", "").strip(),
        "port": port,
        "user": os.getenv("PG_USER", "").strip(),
        "password": os.getenv("PG_PASSWORD", ""),
        "dbname": os.getenv("PG_DB", "").strip(),
        "sslmode": os.getenv("PG_SSLMODE", "prefer").strip(),
        "minconn": minconn,
        "maxconn": maxconn,
        "connect_timeout": connect_timeout,
    }


def get_connection_pool() -> pool.ThreadedConnectionPool:
    """
    Initializes or returns the thread-safe singleton ThreadedConnectionPool.
    Includes TCP keepalives to prevent idle socket drop by Cloud SQL / NAT proxies.
    """
    global _CONNECTION_POOL
    if _CONNECTION_POOL is None or _CONNECTION_POOL.closed:
        config = get_db_config()
        try:
            _CONNECTION_POOL = pool.ThreadedConnectionPool(
                minconn=config["minconn"],
                maxconn=config["maxconn"],
                host=config["host"],
                port=config["port"],
                user=config["user"],
                password=config["password"],
                dbname=config["dbname"],
                sslmode=config["sslmode"],
                connect_timeout=config["connect_timeout"],
                keepalives=1,
                keepalives_idle=30,
                keepalives_interval=10,
                keepalives_count=3,
            )
            logger.info(
                f"Initialized ThreadedConnectionPool ({config['minconn']}-{config['maxconn']} connections) "
                f"to {config['host']}:{config['port']}/{config['dbname']}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL Connection Pool: {e}")
            raise
    return _CONNECTION_POOL


@contextmanager
def get_db_connection() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager for checking out and returning connections from the pool.
    - Performs pre-ping health validation (SELECT 1;) to recover stale/idle sockets.
    - Auto-commits transaction upon successful block execution.
    - Auto-rolls back transaction on exception.
    - Guarantees connection return via pool.putconn() in a finally block.
    """
    conn_pool = get_connection_pool()
    conn = None
    is_broken = False
    
    try:
        conn = conn_pool.getconn()
        
        # Pre-ping health check (recovers 3 AM silent TCP drops from Cloud SQL / NAT)
        try:
            with conn.cursor() as ping_cur:
                ping_cur.execute("SELECT 1;")
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as ping_err:
            logger.warning(f"Detected stale connection from pool ({ping_err}). Discarding and reconnecting...")
            conn_pool.putconn(conn, close=True)
            conn = conn_pool.getconn()

        yield conn
        conn.commit()
    except Exception as exc:
        if conn:
            try:
                conn.rollback()
            except Exception:
                is_broken = True
        logger.error(f"Database transaction error: {exc}")
        raise
    finally:
        if conn and conn_pool and not conn_pool.closed:
            conn_pool.putconn(conn, close=is_broken)


def init_db() -> None:
    """
    Initializes PostgreSQL database schema (video_tags table and indexes) idempotently.
    """
    ddl = """
    CREATE TABLE IF NOT EXISTS video_tags (
        id BIGSERIAL PRIMARY KEY,
        filename VARCHAR(512) NOT NULL UNIQUE,
        filepath TEXT NOT NULL,
        domain VARCHAR(100) NOT NULL DEFAULT 'Unknown',
        entity VARCHAR(255) NOT NULL DEFAULT 'Unknown',
        viral_features JSONB NOT NULL DEFAULT '[]'::jsonb,
        technical JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE UNIQUE INDEX IF NOT EXISTS idx_video_tags_filename ON video_tags (filename);
    CREATE INDEX IF NOT EXISTS idx_video_tags_domain ON video_tags (domain);
    CREATE INDEX IF NOT EXISTS idx_video_tags_entity ON video_tags (entity);
    CREATE INDEX IF NOT EXISTS idx_video_tags_domain_entity ON video_tags (domain, entity);
    CREATE INDEX IF NOT EXISTS idx_video_tags_viral_features_gin ON video_tags USING GIN (viral_features jsonb_path_ops);
    CREATE INDEX IF NOT EXISTS idx_video_tags_technical_gin ON video_tags USING GIN (technical);
    CREATE INDEX IF NOT EXISTS idx_video_tags_created_at ON video_tags (created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_video_tags_updated_at ON video_tags (updated_at DESC);
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(ddl)
    logger.info("PostgreSQL video_tags schema initialized successfully.")


def insert_video_analytics(filepath: str, tags_json: Union[str, Dict[str, Any]]) -> None:
    """
    Inserts or updates video analytics metadata into PostgreSQL video_tags table.
    Wraps viral_features (list) and technical (dict) with psycopg2.extras.Json.
    Executes ON CONFLICT (filename) DO UPDATE to guarantee idempotent upserts.
    """
    if isinstance(tags_json, str):
        try:
            parsed = json.loads(tags_json)
            tags = parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError as e:
            logger.error(f"Malformed tags JSON string: {e}. Falling back to default taxonomy.")
            tags = {}
    elif isinstance(tags_json, dict):
        tags = tags_json
    else:
        logger.warning(f"Unexpected tags_json type: {type(tags_json)}. Using empty dict.")
        tags = {}

    filename = Path(filepath).name
    domain = tags.get("domain") or "Unknown"
    entity = tags.get("entity") or "Unknown"
    viral_features = tags.get("viral_features")
    if not isinstance(viral_features, list):
        viral_features = []
    
    technical = tags.get("technical")
    if not isinstance(technical, dict):
        technical = {}

    upsert_query = """
    INSERT INTO video_tags (filename, filepath, domain, entity, viral_features, technical, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ON CONFLICT (filename) DO UPDATE SET
        filepath = EXCLUDED.filepath,
        domain = EXCLUDED.domain,
        entity = EXCLUDED.entity,
        viral_features = EXCLUDED.viral_features,
        technical = EXCLUDED.technical,
        updated_at = CURRENT_TIMESTAMP;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                upsert_query,
                (
                    filename,
                    str(filepath),
                    str(domain),
                    str(entity),
                    Json(viral_features),
                    Json(technical),
                ),
            )
    logger.info(f"Successfully synced video analytics for '{filename}' to PostgreSQL.")


def close_pool() -> None:
    """
    Gracefully closes all connections in the ThreadedConnectionPool.
    Called upon daemon termination or module teardown.
    """
    global _CONNECTION_POOL
    if _CONNECTION_POOL is not None and not _CONNECTION_POOL.closed:
        _CONNECTION_POOL.closeall()
        _CONNECTION_POOL = None
        logger.info("Closed all connections in ThreadedConnectionPool.")


# Register clean shutdown on interpreter exit
atexit.register(close_pool)


if __name__ == "__main__":
    init_db()
