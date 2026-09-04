"""
db_client.py - Shared PostgreSQL Client for Firebase Data Connect / Cloud SQL.
Provides connection pooling, context management, and CRUD helpers for the video_tags schema.
Strictly enforces Rule R26 (Fail-Fast Environment Authentication Guardrail).
"""

import os
import json
import logging
import atexit
from pathlib import Path
from typing import Union, Dict, Any, List, Optional, Generator
from contextlib import contextmanager
from dotenv import load_dotenv

# Try importing psycopg2, but provide clean fallback if missing
try:
    import psycopg2
    from psycopg2 import pool, extras
    from psycopg2.extras import Json, RealDictCursor
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False
    pool = None
    extras = None
    Json = None
    RealDictCursor = None

# Configure module logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s - [%(levelname)s] - [dataconnect.db_client] - %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

# Rule R26: Explicitly load .env file from workspace root or current directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATHS = [
    PROJECT_ROOT / ".env",
    Path(__file__).resolve().parent / ".env",
    Path.cwd() / ".env"
]
for env_p in ENV_PATHS:
    if env_p.exists():
        load_dotenv(dotenv_path=env_p, override=False)

REQUIRED_ENV_VARS = ["PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DB"]

# Global singleton connection pool
_CONNECTION_POOL: Optional[Any] = None


class AuthGuardrailError(ValueError):
    """Raised when database credentials fail Rule R26 authentication guardrails."""
    pass


AuthGuardrailViolation = AuthGuardrailError


def validate_db_env(env_dict: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Validates PostgreSQL configuration adhering to Rule R26.
    Fails fast with a loud ValueError if any required environment variable is missing or empty.
    """
    for env_p in ENV_PATHS:
        if env_p.exists():
            load_dotenv(dotenv_path=env_p, override=False)

    get_val = (lambda k: env_dict.get(k)) if env_dict is not None else (lambda k: os.getenv(k))

    missing = [var for var in REQUIRED_ENV_VARS if not get_val(var) or not str(get_val(var)).strip()]
    if missing:
        error_msg = (
            f"R26 Guardrail Violation: Missing required PostgreSQL database credentials in .env: {missing}. "
            f"Adhering to Workspace Rule R26 (The Background Daemon Auth Guardrail), "
            f"the pipeline is halted immediately to prevent silent data loss."
        )
        logger.error(error_msg)
        raise AuthGuardrailError(error_msg)

    raw_port = get_val("PG_PORT") or "5432"
    try:
        port = int(str(raw_port).strip())
    except ValueError:
        raise ValueError(f"Invalid PG_PORT value '{raw_port}': must be an integer.")

    raw_min = get_val("PG_MIN_CONN") or "1"
    raw_max = get_val("PG_MAX_CONN") or "10"
    raw_timeout = get_val("PG_CONNECT_TIMEOUT") or "10"

    try:
        minconn = int(str(raw_min).strip())
        maxconn = int(str(raw_max).strip())
        connect_timeout = int(str(raw_timeout).strip())
    except ValueError as e:
        raise ValueError(f"Invalid pool/timeout configuration: {e}")

    return {
        "host": str(get_val("PG_HOST")).strip(),
        "port": port,
        "user": str(get_val("PG_USER")).strip(),
        "password": str(get_val("PG_PASSWORD")),
        "dbname": str(get_val("PG_DB")).strip(),
        "sslmode": str(get_val("PG_SSLMODE") or "prefer").strip(),
        "minconn": minconn,
        "maxconn": maxconn,
        "connect_timeout": connect_timeout,
    }


def get_db_config() -> Dict[str, Any]:
    """Loads and returns current database configuration."""
    return validate_db_env()


def get_connection_pool() -> Any:
    """
    Initializes or returns the thread-safe singleton ThreadedConnectionPool.
    Includes TCP keepalives to prevent idle socket drops by Cloud SQL or NAT proxies.
    """
    global _CONNECTION_POOL
    if not PSYCOPG2_AVAILABLE:
        raise RuntimeError("psycopg2 is not installed. Please install psycopg2-binary to use db_client.")

    if _CONNECTION_POOL is None or getattr(_CONNECTION_POOL, 'closed', True):
        config = validate_db_env()
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
                f"Initialized ThreadedConnectionPool ({config['minconn']}-{config['maxconn']} conns) "
                f"to {config['host']}:{config['port']}/{config['dbname']}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL Connection Pool: {e}")
            raise
    return _CONNECTION_POOL


@contextmanager
def get_db_connection() -> Generator[Any, None, None]:
    """
    Context manager for checking out and returning connections from the pool.
    - Pre-ping health check (SELECT 1;) to recover stale/idle sockets.
    - Auto-commits transaction on success.
    - Auto-rolls back transaction on exception.
    - Guarantees connection return via pool.putconn() in finally.
    """
    conn_pool = get_connection_pool()
    conn = None
    is_broken = False

    try:
        conn = conn_pool.getconn()
        try:
            with conn.cursor() as ping_cur:
                ping_cur.execute("SELECT 1;")
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as ping_err:
            logger.warning(f"Detected stale connection ({ping_err}). Reconnecting...")
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
        if conn and conn_pool and not getattr(conn_pool, 'closed', False):
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


def insert_video_tag(
    filename: Optional[str] = None,
    filepath: Optional[str] = None,
    domain: str = "Unknown",
    entity: str = "Unknown",
    viral_features: Optional[Union[Dict[str, Any], List[Any], str]] = None,
    technical: Optional[Union[Dict[str, Any], List[Any], str]] = None,
    **kwargs
) -> Optional[int]:
    """
    Inserts or updates a video tag record in the video_tags table.
    Supports flexible arguments (including filepath-only with tags_json in kwargs).
    """
    if filename is None and filepath is not None:
        filename = Path(filepath).name
    elif filename is not None and filepath is None:
        filepath = filename

    if not filename or not filepath:
        raise ValueError("Both filename and filepath must be provided or derivable.")

    if "tags_json" in kwargs:
        tags = kwargs["tags_json"]
        if isinstance(tags, str):
            try:
                tags = json.loads(tags)
            except Exception:
                tags = {}
        if isinstance(tags, dict):
            domain = tags.get("domain", domain)
            entity = tags.get("entity", entity)
            if viral_features is None:
                viral_features = tags.get("viral_features", [])
            if technical is None:
                technical = tags.get("technical", {})

    if viral_features is None:
        viral_features = []
    elif isinstance(viral_features, str):
        try:
            viral_features = json.loads(viral_features)
        except Exception:
            viral_features = [viral_features]

    if technical is None:
        technical = {}
    elif isinstance(technical, str):
        try:
            technical = json.loads(technical)
        except Exception:
            technical = {"raw": technical}

    upsert_sql = """
    INSERT INTO video_tags (filename, filepath, domain, entity, viral_features, technical, updated_at)
    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ON CONFLICT (filename) DO UPDATE SET
        filepath = EXCLUDED.filepath,
        domain = EXCLUDED.domain,
        entity = EXCLUDED.entity,
        viral_features = EXCLUDED.viral_features,
        technical = EXCLUDED.technical,
        updated_at = CURRENT_TIMESTAMP
    RETURNING id;
    """

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                upsert_sql,
                (
                    str(filename),
                    str(filepath),
                    str(domain or "Unknown"),
                    str(entity or "Unknown"),
                    Json(viral_features),
                    Json(technical),
                ),
            )
            row = cur.fetchone()
            return row[0] if row else None


# Backward compatibility alias
insert_video_analytics = insert_video_tag


def query_video_tags(
    domain: Optional[str] = None,
    entity: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Queries video_tags records with optional domain/entity filtering and pagination.
    Returns a list of dictionaries.
    """
    query = ["SELECT id, filename, filepath, domain, entity, viral_features, technical, created_at, updated_at FROM video_tags"]
    params: List[Any] = []
    where_clauses: List[str] = []

    if domain:
        where_clauses.append("domain = %s")
        params.append(domain)
    if entity:
        where_clauses.append("entity = %s")
        params.append(entity)

    if where_clauses:
        query.append("WHERE " + " AND ".join(where_clauses))

    query.append("ORDER BY created_at DESC LIMIT %s OFFSET %s")
    params.extend([limit, offset])

    sql = " ".join(query)

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def list_video_tags(domain: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Alias for query_video_tags for high-level callers."""
    return query_video_tags(domain=domain, limit=limit)


def get_video_tag(filename: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single video tag record by filename."""
    sql = """
    SELECT id, filename, filepath, domain, entity, viral_features, technical, created_at, updated_at
    FROM video_tags
    WHERE filename = %s
    LIMIT 1;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (str(filename),))
            row = cur.fetchone()
            return dict(row) if row else None


def get_video_tag_by_id(tag_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves a single video tag record by its primary key ID."""
    sql = """
    SELECT id, filename, filepath, domain, entity, viral_features, technical, created_at, updated_at
    FROM video_tags
    WHERE id = %s
    LIMIT 1;
    """
    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (tag_id,))
            row = cur.fetchone()
            return dict(row) if row else None


def close_pool() -> None:
    """Gracefully closes all connections in the ThreadedConnectionPool."""
    global _CONNECTION_POOL
    if _CONNECTION_POOL is not None and not getattr(_CONNECTION_POOL, 'closed', False):
        try:
            _CONNECTION_POOL.closeall()
            logger.info("Closed all connections in ThreadedConnectionPool.")
        except Exception as e:
            logger.warning(f"Error closing connection pool: {e}")
        finally:
            _CONNECTION_POOL = None


atexit.register(close_pool)

if __name__ == '__main__':
    try:
        init_db()
    except AuthGuardrailError as age:
        logger.info(f"Guardrail check confirmed: {age}")
