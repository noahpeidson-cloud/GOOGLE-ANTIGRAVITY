"""
test_database_sink.py - Comprehensive Unit, Integration, and Adversarial Test Suite
for Quick Share AI Loop PostgreSQL Migration (database_sink.py).

Implements Loud Assertions, deterministic mocking, and verifies:
- Tier 1: Core Feature Coverage (Auth validation, pool creation, DDL execution, upsert, shutdown)
- Tier 2: Boundary & Corner Cases (Port conversions, None/empty JSONB values, Windows filepaths)
- Tier 3: Cross-Feature Combinations (JSON string vs dict, rollback on failure, concurrency)
- Tier 4: Real-World Workloads (4K 60fps EDM/Sports/Travel taxonomy, schema contracts)
- Tier 5: Adversarial & Red Team Hardening (Pre-ping recovery, zero-leak on repeat failures, unrecoverable socket teardown)
"""

import os
import json
import threading
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, call
import psycopg2
from psycopg2.extras import Json

import database_sink
from database_sink import (
    get_db_config,
    get_connection_pool,
    get_db_connection,
    init_db,
    insert_video_analytics,
    close_pool,
)


# =============================================================================
# TIER 1: CORE FEATURE COVERAGE
# =============================================================================

def test_get_db_config_success(monkeypatch):
    """Tier 1: Proves get_db_config parses all valid environment variables correctly."""
    monkeypatch.setenv("PG_HOST", "cloudsql.internal")
    monkeypatch.setenv("PG_PORT", "5433")
    monkeypatch.setenv("PG_USER", "db_admin")
    monkeypatch.setenv("PG_PASSWORD", "super_secret_pw")
    monkeypatch.setenv("PG_DB", "quick_share_prod")
    monkeypatch.setenv("PG_SSLMODE", "require")
    monkeypatch.setenv("PG_MIN_CONN", "2")
    monkeypatch.setenv("PG_MAX_CONN", "20")
    monkeypatch.setenv("PG_CONNECT_TIMEOUT", "15")

    config = get_db_config()

    assert config["host"] == "cloudsql.internal"
    assert config["port"] == 5433
    assert config["user"] == "db_admin"
    assert config["password"] == "super_secret_pw"
    assert config["dbname"] == "quick_share_prod"
    assert config["sslmode"] == "require"
    assert config["minconn"] == 2
    assert config["maxconn"] == 20
    assert config["connect_timeout"] == 15


@pytest.mark.parametrize("missing_var", ["PG_HOST", "PG_USER", "PG_PASSWORD", "PG_DB"])
def test_get_db_config_missing_required_vars_raises_value_error(monkeypatch, missing_var):
    """Tier 1: Proves Rule R26 fail-fast when any mandatory PG_* credential is missing or empty."""
    monkeypatch.delenv(missing_var, raising=False)

    with pytest.raises(ValueError) as exc_info:
        get_db_config()

    err_str = str(exc_info.value)
    assert "FATAL: Missing required PostgreSQL environment variables" in err_str
    assert missing_var in err_str
    assert "Rule R26" in err_str


@patch("database_sink.pool.ThreadedConnectionPool")
def test_get_connection_pool_singleton_initialization(mock_pool_cls):
    """Tier 1: Proves get_connection_pool initializes a singleton ThreadedConnectionPool with keepalives."""
    mock_pool_instance = MagicMock()
    mock_pool_instance.closed = False
    mock_pool_cls.return_value = mock_pool_instance

    pool1 = get_connection_pool()
    pool2 = get_connection_pool()

    assert pool1 is mock_pool_instance
    assert pool2 is mock_pool_instance
    assert mock_pool_cls.call_count == 1

    # Verify TCP keepalives and DSN arguments were passed
    _, kwargs = mock_pool_cls.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 5432
    assert kwargs["user"] == "postgres"
    assert kwargs["dbname"] == "media_analytics"
    assert kwargs["keepalives"] == 1
    assert kwargs["keepalives_idle"] == 30
    assert kwargs["keepalives_interval"] == 10
    assert kwargs["keepalives_count"] == 3


@patch("database_sink.pool.ThreadedConnectionPool")
def test_init_db_executes_ddl_and_indexes(mock_pool_cls, mock_pg_pool):
    """Tier 1: Proves init_db executes DDL table creation and GIN indexes."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    init_db()

    assert mock_cur.execute.called
    executed_statements = [call_arg[0][0] for call_arg in mock_cur.execute.call_args_list]
    combined_sql = " ".join(executed_statements)

    assert "CREATE TABLE IF NOT EXISTS video_tags" in combined_sql
    assert "viral_features JSONB" in combined_sql
    assert "technical JSONB" in combined_sql
    assert "idx_video_tags_viral_features_gin" in combined_sql
    assert "idx_video_tags_technical_gin" in combined_sql


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_basic_dict(mock_pool_cls, mock_pg_pool):
    """Tier 1: Proves basic insert_video_analytics execution with dict input."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_conn = mock_pg_pool["conn"]
    mock_cur = mock_pg_pool["cur"]

    payload = {
        "domain": "EDM",
        "entity": "Subtronics",
        "viral_features": ["Heavy_Lasers", "Bass_Drop_0:30"],
        "technical": {"lighting": "dark", "fps": 60},
    }

    filepath = "C:/Users/noahp/Downloads/Quick Share/subtronics_clip.mp4"
    insert_video_analytics(filepath, payload)

    assert mock_cur.execute.called
    args, _ = mock_cur.execute.call_args
    sql, params = args

    assert "INSERT INTO video_tags" in sql
    assert "ON CONFLICT (filename) DO UPDATE SET" in sql
    assert params[0] == "subtronics_clip.mp4"
    assert params[1] == filepath
    assert params[2] == "EDM"
    assert params[3] == "Subtronics"
    assert isinstance(params[4], Json)
    assert params[4].adapted == ["Heavy_Lasers", "Bass_Drop_0:30"]
    assert isinstance(params[5], Json)
    assert params[5].adapted == {"lighting": "dark", "fps": 60}

    assert mock_conn.commit.called
    mock_pg_pool["pool"].putconn.assert_called_with(mock_conn, close=False)


@patch("database_sink.pool.ThreadedConnectionPool")
def test_close_pool_terminates_all_connections(mock_pool_cls, mock_pg_pool):
    """Tier 1: Proves close_pool invokes closeall() on pool and resets singleton."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]

    # Initialize pool
    pool_instance = get_connection_pool()
    assert database_sink._CONNECTION_POOL is not None

    close_pool()

    assert mock_pg_pool["pool"].closeall.called
    assert database_sink._CONNECTION_POOL is None


# =============================================================================
# TIER 2: BOUNDARY & CORNER CASES
# =============================================================================

def test_get_db_config_port_fallback_and_whitespace(monkeypatch):
    """Tier 2: Validates whitespace stripping and default fallback for PG_PORT."""
    monkeypatch.setenv("PG_PORT", "   5439   ")
    config = get_db_config()
    assert config["port"] == 5439

    monkeypatch.setenv("PG_PORT", "")
    config = get_db_config()
    assert config["port"] == 5432


def test_get_db_config_invalid_port_raises_value_error(monkeypatch):
    """Tier 2: Validates non-integer PG_PORT raises descriptive ValueError."""
    monkeypatch.setenv("PG_PORT", "not_a_port")
    with pytest.raises(ValueError) as exc_info:
        get_db_config()
    assert "Invalid PG_PORT value 'not_a_port'" in str(exc_info.value)


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_none_or_empty_viral_features(mock_pool_cls, mock_pg_pool):
    """Tier 2: Proves None or non-list viral_features defaults to [] and wraps in Json([])."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    payload = {
        "domain": "Travel",
        "entity": "Tokyo",
        "viral_features": None,  # None instead of list
        "technical": {"weather": "rainy"},
    }

    insert_video_analytics("tokyo_shibuya.mp4", payload)

    args, _ = mock_cur.execute.call_args
    _, params = args
    assert isinstance(params[4], Json)
    assert params[4].adapted == []


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_none_or_empty_technical(mock_pool_cls, mock_pg_pool):
    """Tier 2: Proves None or non-dict technical field defaults to {} and wraps in Json({})."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    payload = {
        "domain": "Sports Cards",
        "entity": "Caitlin Clark",
        "viral_features": ["1st_Bowman_Auto", "PSA_10_Gem_Mint"],
        "technical": None,  # None instead of dict
    }

    insert_video_analytics("caitlin_clark_bowman.mp4", payload)

    args, _ = mock_cur.execute.call_args
    _, params = args
    assert isinstance(params[5], Json)
    assert params[5].adapted == {}


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_windows_path_with_backslashes(mock_pool_cls, mock_pg_pool):
    """Tier 2: Verifies proper extraction and storage of Windows filepaths with backslashes."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    win_path = r"C:\Users\noahp\Downloads\Quick Share\20260819_212636.mp4"
    insert_video_analytics(win_path, {"domain": "EDM", "entity": "Excision"})

    args, _ = mock_cur.execute.call_args
    _, params = args
    assert params[0] == "20260819_212636.mp4"
    assert params[1] == win_path


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_missing_domain_and_entity_default_unknown(mock_pool_cls, mock_pg_pool):
    """Tier 2: Verifies missing or None domain and entity default to 'Unknown'."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    insert_video_analytics("unknown_video.mp4", {})

    args, _ = mock_cur.execute.call_args
    _, params = args
    assert params[2] == "Unknown"
    assert params[3] == "Unknown"


# =============================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_stringified_json_input(mock_pool_cls, mock_pg_pool):
    """Tier 3: Proves stringified JSON payload is correctly decoded and sunk as JSONB."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    raw_json_str = json.dumps({
        "domain": "Sports Cards",
        "entity": "Victor Wembanyama",
        "viral_features": ["Prizm_Silver_RC", "Case_Hit", "Downtown"],
        "technical": {"centering": "50/50", "corners": "sharp"},
    })

    insert_video_analytics("wemby_case_hit.mp4", raw_json_str)

    args, _ = mock_cur.execute.call_args
    _, params = args
    assert params[2] == "Sports Cards"
    assert params[3] == "Victor Wembanyama"
    assert isinstance(params[4], Json)
    assert params[4].adapted == ["Prizm_Silver_RC", "Case_Hit", "Downtown"]
    assert isinstance(params[5], Json)
    assert params[5].adapted == {"centering": "50/50", "corners": "sharp"}


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_malformed_json_fallback(mock_pool_cls, mock_pg_pool):
    """Tier 3: Proves malformed JSON string triggers safe fallback without crashing."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    malformed_json = "{bad_json: True, missing_quotes"
    insert_video_analytics("corrupt_metadata.mp4", malformed_json)

    args, _ = mock_cur.execute.call_args
    _, params = args
    assert params[0] == "corrupt_metadata.mp4"
    assert params[2] == "Unknown"
    assert params[3] == "Unknown"
    assert params[4].adapted == []
    assert params[5].adapted == {}


@patch("database_sink.pool.ThreadedConnectionPool")
@pytest.mark.parametrize(
    "stringified_non_dict_json",
    [
        '["item1", "item2"]',
        '12345',
        '99.99',
        'true',
        'false',
        'null',
        '"just a plain string"',
    ],
)
def test_insert_video_analytics_stringified_non_dict_json_fallback(
    mock_pool_cls, mock_pg_pool, stringified_non_dict_json
):
    """Tier 3: Proves stringified non-dict JSON payloads safely fall back to default taxonomy without AttributeError."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    insert_video_analytics("sample_non_dict.mp4", stringified_non_dict_json)

    assert mock_cur.execute.called
    args, _ = mock_cur.execute.call_args
    _, params = args
    assert params[0] == "sample_non_dict.mp4"
    assert params[2] == "Unknown"
    assert params[3] == "Unknown"
    assert isinstance(params[4], Json)
    assert params[4].adapted == []
    assert isinstance(params[5], Json)
    assert params[5].adapted == {}


@patch("database_sink.pool.ThreadedConnectionPool")
def test_get_db_connection_transaction_rollback_on_query_error(mock_pool_cls, mock_pg_pool):
    """Tier 3: Proves transaction rolls back on SQL error and connection is returned to pool."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_conn = mock_pg_pool["conn"]
    mock_cur = mock_pg_pool["cur"]

    def execute_side_effect(query, *args, **kwargs):
        if query.strip().startswith("SELECT 1"):
            return None
        raise psycopg2.DatabaseError("Syntax error in query")

    mock_cur.execute.side_effect = execute_side_effect

    with pytest.raises(psycopg2.DatabaseError):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT * FROM non_existent_table;")

    # Loud Assertions
    assert mock_conn.rollback.called
    assert not mock_conn.commit.called
    mock_pg_pool["pool"].putconn.assert_called_with(mock_conn, close=False)


@patch("database_sink.pool.ThreadedConnectionPool")
def test_concurrent_threaded_pool_checkouts(mock_pool_cls):
    """Tier 3: Proves ThreadedConnectionPool operates safely across concurrent worker threads."""
    mock_pool_instance = MagicMock()
    mock_pool_instance.closed = False
    mock_pool_cls.return_value = mock_pool_instance

    connections = [MagicMock() for _ in range(5)]
    for c in connections:
        c.cursor.return_value.__enter__.return_value = MagicMock()
    mock_pool_instance.getconn.side_effect = connections * 2

    results = []

    def worker(worker_id):
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            results.append(f"Worker {worker_id} success")
        except Exception as e:
            results.append(f"Worker {worker_id} failed: {e}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 5
    assert all("success" in r for r in results)
    assert mock_pool_instance.putconn.call_count == 5


# =============================================================================
# TIER 4: REAL-WORLD APPLICATION WORKLOADS
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_video_analytics_4k_edm_concert_payload(mock_pool_cls, mock_pg_pool):
    """Tier 4: Proves ingestion of complex 4K 60fps EDM festival footage taxonomy."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_conn = mock_pg_pool["conn"]
    mock_cur = mock_pg_pool["cur"]

    payload = {
        "domain": "EDM",
        "entity": "Excision Lost Lands 2026",
        "viral_features": [
            "Heavy_Lasers",
            "Bass_Drop_0:15",
            "Crowd_Pan",
            "Stage_Lighting",
            "Synchronized_Lights",
            "Pyrotechnics_0:45",
        ],
        "technical": {
            "resolution": "3840x2160",
            "fps": 60,
            "bitrate_mbps": 120,
            "lighting": "dynamic_lasers",
            "audio_clipping": False,
            "orientation": "vertical",
            "camera_stability": "handheld_stabilized",
        },
    }

    filepath = "G:/My Drive/GOOGLE ANTIGRAVITY/photos_triage_project/Raw_Ingest/20260819_212636_4K.mp4"
    insert_video_analytics(filepath, payload)

    assert mock_cur.execute.called
    args, _ = mock_cur.execute.call_args
    sql, params = args

    assert params[0] == "20260819_212636_4K.mp4"
    assert params[1] == filepath
    assert params[2] == "EDM"
    assert params[3] == "Excision Lost Lands 2026"
    assert len(params[4].adapted) == 6
    assert "Heavy_Lasers" in params[4].adapted
    assert params[5].adapted["resolution"] == "3840x2160"
    assert params[5].adapted["audio_clipping"] is False
    assert mock_conn.commit.called


def test_schema_sql_file_exists_and_contains_gin_indexes():
    """Tier 4: Proves schema.sql file exists and specifies JSONB columns & GIN index directives."""
    schema_path = Path(__file__).resolve().parent.parent / "schema.sql"
    assert schema_path.exists(), f"schema.sql not found at {schema_path}"

    content = schema_path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS video_tags" in content
    assert "viral_features JSONB NOT NULL DEFAULT '[]'::jsonb" in content
    assert "technical JSONB NOT NULL DEFAULT '{}'::jsonb" in content
    assert "USING GIN (viral_features jsonb_path_ops)" in content
    assert "USING GIN (technical)" in content
    assert "idx_video_tags_filename" in content


def test_schema_gql_file_exists_and_has_data_connect_directives():
    """Tier 4: Proves schema.gql file exists and defines Firebase Data Connect schema."""
    schema_gql_path = Path(__file__).resolve().parent.parent / "schema.gql"
    assert schema_gql_path.exists(), f"schema.gql not found at {schema_gql_path}"

    content = schema_gql_path.read_text(encoding="utf-8")
    assert "type VideoTag @table" in content
    assert 'viralFeatures: Any! @col(name: "viral_features", dataType: "jsonb")' in content
    assert 'technical: Any! @col(name: "technical", dataType: "jsonb")' in content


# =============================================================================
# TIER 5: ADVERSARIAL & RED TEAM HARDENING
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
def test_stale_connection_pre_ping_recovery_3am_syndrome(mock_pool_cls):
    """Tier 5: Proves pre-ping recovers from silent Cloud SQL 3 AM TCP drops."""
    mock_pool_instance = MagicMock()
    mock_pool_instance.closed = False
    mock_pool_cls.return_value = mock_pool_instance

    dead_conn = MagicMock()
    dead_cur = MagicMock()
    dead_conn.cursor.return_value.__enter__.return_value = dead_cur
    dead_cur.execute.side_effect = psycopg2.OperationalError("server closed the connection unexpectedly")

    fresh_conn = MagicMock()
    fresh_cur = MagicMock()
    fresh_conn.cursor.return_value.__enter__.return_value = fresh_cur
    fresh_cur.execute.return_value = None

    mock_pool_instance.getconn.side_effect = [dead_conn, fresh_conn]

    with get_db_connection() as conn:
        assert conn is fresh_conn

    # Dead connection discarded with close=True
    mock_pool_instance.putconn.assert_any_call(dead_conn, close=True)
    # Fresh connection returned cleanly with close=False
    mock_pool_instance.putconn.assert_any_call(fresh_conn, close=False)


@patch("database_sink.pool.ThreadedConnectionPool")
def test_pool_starvation_prevention_on_repeated_errors(mock_pool_cls, mock_pg_pool):
    """Tier 5: Proves 0 connection leaks across 20 consecutive query failures."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_conn = mock_pg_pool["conn"]
    mock_cur = mock_pg_pool["cur"]

    def execute_side_effect(query, *args, **kwargs):
        if query.strip().startswith("SELECT 1"):
            return None
        raise psycopg2.DatabaseError("Foreign key constraint violation")

    mock_cur.execute.side_effect = execute_side_effect

    for i in range(20):
        with pytest.raises(psycopg2.DatabaseError):
            insert_video_analytics(f"failure_video_{i}.mp4", {"domain": "EDM"})

    # Every single iteration MUST have put the connection back in the pool
    assert mock_pg_pool["pool"].putconn.call_count == 20
    assert mock_conn.rollback.call_count == 20


@patch("database_sink.pool.ThreadedConnectionPool")
def test_broken_connection_rollback_failure_marks_close_true(mock_pool_cls, mock_pg_pool):
    """Tier 5: Proves unrecoverable rollback exception marks connection as broken and closes socket."""
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_conn = mock_pg_pool["conn"]
    mock_cur = mock_pg_pool["cur"]

    def execute_side_effect(query, *args, **kwargs):
        if query.strip().startswith("SELECT 1"):
            return None
        raise psycopg2.DatabaseError("Fatal network error")

    mock_cur.execute.side_effect = execute_side_effect
    mock_conn.rollback.side_effect = psycopg2.InterfaceError("Connection is dead during rollback")

    with pytest.raises(psycopg2.DatabaseError):
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE video_tags SET domain = 'fail';")

    mock_pg_pool["pool"].putconn.assert_called_with(mock_conn, close=True)


@patch("database_sink.pool.ThreadedConnectionPool")
def test_close_pool_idempotent_and_safe_when_uninitialized(mock_pool_cls):
    """Tier 5: Proves close_pool is completely idempotent and safe when called repeatedly."""
    database_sink._CONNECTION_POOL = None
    close_pool()  # No error when None
    close_pool()

    mock_pool_instance = MagicMock()
    mock_pool_instance.closed = False
    database_sink._CONNECTION_POOL = mock_pool_instance

    close_pool()
    assert mock_pool_instance.closeall.call_count == 1
    assert database_sink._CONNECTION_POOL is None

    # Call again after close
    close_pool()
    assert mock_pool_instance.closeall.call_count == 1
