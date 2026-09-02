"""
test_adversarial_payloads.py - Adversarial Stress & Integrity Test Suite
for Quick Share AI Loop PostgreSQL Migration (database_sink.py).

Engineered by Challenger 2 (Empirical Challenger).
Stress-tests JSONB boundary limits, deeply nested structures, massive arrays,
Unicode/emojis/special characters, SQL injection robustness, malformed inputs,
non-dict top-level JSON types, Windows paths, and upsert conflict integrity.
"""

import os
import json
import math
from pathlib import Path
from unittest.mock import patch, MagicMock, call
import pytest
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
# SUITE 1: MASSIVE 4K VIDEO PAYLOADS & DEEP NESTING STRESS TESTS
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_massive_viral_features_1500_elements(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 1.1: Stress-test insert with 1,500+ viral features and complex telemetry.
    Ensures serialization does not choke or truncate massive array payloads.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    viral_features = [
        f"Laser_Burst_Frame_{i}_Intensity_{i * 1.5:.2f}_Timestamp_{i // 60:02d}:{i % 60:02d}"
        for i in range(1500)
    ]

    payload = {
        "domain": "EDM",
        "entity": "Excision Paradox 4K",
        "viral_features": viral_features,
        "technical": {
            "resolution": "3840x2160",
            "fps": 60,
            "bitrate_mbps": 150,
            "total_frames_analyzed": 1500,
        },
    }

    filepath = "G:/My Drive/GOOGLE ANTIGRAVITY/4K_Ingest/massive_lasers_1500.mp4"
    insert_video_analytics(filepath, payload)

    assert mock_cur.execute.called
    sql, params = mock_cur.execute.call_args[0]

    assert params[0] == "massive_lasers_1500.mp4"
    assert params[1] == filepath
    assert params[2] == "EDM"
    assert params[3] == "Excision Paradox 4K"
    assert isinstance(params[4], Json)
    assert len(params[4].adapted) == 1500
    assert params[4].adapted[0] == "Laser_Burst_Frame_0_Intensity_0.00_Timestamp_00:00"
    assert params[4].adapted[1499] == "Laser_Burst_Frame_1499_Intensity_2248.50_Timestamp_24:59"
    assert params[5].adapted["total_frames_analyzed"] == 1500


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_ultra_massive_viral_features_10000_elements(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 1.2: Extreme stress test with 10,000 elements in viral_features.
    Verifies memory stability and psycopg2 Json adaptation at 10k scale.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    huge_features = [
        {
            "tag_id": idx,
            "label": f"Crowd_Reaction_{idx}",
            "confidence": 0.998,
            "bounding_box": [10, 20, 1920, 1080],
            "metadata": {"source": "gemini-3.6-flash", "pass": 1},
        }
        for idx in range(10000)
    ]

    payload = {
        "domain": "Sports Cards",
        "entity": "National Sports Collectors Convention 2026",
        "viral_features": huge_features,
        "technical": {"camera": "Sony FX3", "codec": "ProRes 422 HQ"},
    }

    insert_video_analytics("huge_convention_walkthrough.mov", payload)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]
    assert isinstance(params[4], Json)
    assert len(params[4].adapted) == 10000
    assert params[4].adapted[9999]["label"] == "Crowd_Reaction_9999"


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_deeply_nested_technical_object(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 1.3: Deeply nested JSON dictionary (25+ levels).
    Verifies recursive JSON adaptation does not hit recursion limits.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    deep_dict = {"leaf": "4K_HDR10_Rec2020_Matrix"}
    for level in range(25, 0, -1):
        deep_dict = {f"level_{level}": deep_dict, f"meta_{level}": level * 10}

    payload = {
        "domain": "Content Creation",
        "entity": "HDR Color Grading Pipeline",
        "viral_features": ["Rec2020", "HDR10_PQ", "Wide_Gamut"],
        "technical": deep_dict,
    }

    insert_video_analytics("hdr_color_profile.mov", payload)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]
    assert isinstance(params[5], Json)

    # Traverse 25 levels down to verify integrity
    curr = params[5].adapted
    for level in range(1, 26):
        assert f"meta_{level}" in curr
        assert curr[f"meta_{level}"] == level * 10
        curr = curr[f"level_{level}"]
    assert curr == {"leaf": "4K_HDR10_Rec2020_Matrix"}


# =============================================================================
# SUITE 2: UNICODE, EMOJIS, SPECIAL CHARACTERS & SQL INJECTION RESILIENCE
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_unicode_emojis_and_multilingual_metadata(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 2.1: Payloads containing multi-byte UTF-8, Japanese, Cyrillic,
    Arabic, German umlauts, complex emojis, and ZWJ sequences.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    payload = {
        "domain": "Travel ✈️ 🌍 & EDM 🎛️⚡",
        "entity": "東京ドーム 2026 (Tokyo Dome) 🇯🇵 & München Biergarten 🇩🇪 & مهرجان 🎵",
        "viral_features": [
            "🔥 Heavy_Lasers_レーザー",
            "🚀 Bass_Drop_Бас_Дроп",
            "👨‍👩‍👧‍👦 Crowd_Wave_семья",
            "💎 PSA_10_Gem_Mint_10点満点_💯",
            "موسيقى_حماسية_Bass",
            "Café_Crème_Brûlée_☕",
        ],
        "technical": {
            "resolution": "3840x2160 (4K UHD)",
            "color_space": "DCI-P3 廣色域",
            "notes": "Testing Unicode boundaries: ñ, ü, é, å, ø, ç, ß, 漢字, ひらがな, Русский, العربية",
        },
    }

    filepath = "G:/My Drive/GOOGLE ANTIGRAVITY/videos/🔥_EDC_東京_2026_4K_[60fps]_#1.mp4"
    insert_video_analytics(filepath, payload)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]

    assert params[0] == "🔥_EDC_東京_2026_4K_[60fps]_#1.mp4"
    assert params[1] == filepath
    assert "✈️" in params[2] and "🎛️" in params[2]
    assert "東京ドーム" in params[3] and "München" in params[3]
    assert params[4].adapted[0] == "🔥 Heavy_Lasers_レーザー"
    assert params[4].adapted[3] == "💎 PSA_10_Gem_Mint_10点満点_💯"
    assert "廣色域" in params[5].adapted["color_space"]


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_sql_injection_payload_resilience(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 2.2: Parameterized query robustness against SQL injection attacks
    embedded in filepath, domain, entity, viral_features, and technical keys/values.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    injection_filename = "video'; DROP TABLE video_tags; SELECT * FROM pg_user WHERE '1'='1.mp4"
    injection_filepath = f"C:/Videos/{injection_filename}"

    payload = {
        "domain": "'; DROP TABLE video_tags; --",
        "entity": "' OR 1=1; DELETE FROM video_tags WHERE 'a'='a",
        "viral_features": [
            "1'; TRUNCATE TABLE video_tags; --",
            "Robert'); DROP TABLE Students;--",
            "\" OR \"\"=\"",
        ],
        "technical": {
            "camera'; DROP TABLE video_tags; --": "Sony'; SELECT pg_sleep(10); --",
            "admin_flag": "TRUE' UNION SELECT * FROM users --",
        },
    }

    insert_video_analytics(injection_filepath, payload)

    assert mock_cur.execute.called
    sql, params = mock_cur.execute.call_args[0]

    # Verify query structure uses %s parameters and is NOT string-interpolated
    assert "%s, %s, %s, %s, %s, %s" in sql
    assert "DROP TABLE" not in sql
    assert params[0] == injection_filename
    assert params[1] == injection_filepath
    assert params[2] == "'; DROP TABLE video_tags; --"
    assert params[3] == "' OR 1=1; DELETE FROM video_tags WHERE 'a'='a"
    assert params[4].adapted[0] == "1'; TRUNCATE TABLE video_tags; --"
    assert "Sony'; SELECT pg_sleep(10); --" in params[5].adapted.values()


# =============================================================================
# SUITE 3: MALFORMED INPUTS & TOP-LEVEL NON-DICT JSON HANDLING
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
@pytest.mark.parametrize(
    "corrupt_input",
    [
        "",  # Empty string
        "   \n\t   ",  # Whitespace only
        "INVALID_JSON_CONTENT",  # Random non-JSON string
        "{broken: json, missing_quotes: true",  # Syntax error
        "{'single_quotes': 'invalid_in_json'}",  # Single quotes
        '{"unclosed_string": "value',  # Unclosed string
        '{"nested": {"unclosed": 123}',  # Unclosed bracket
        "undefined",  # JavaScript undefined
        "<html><body>500 Internal Server Error</body></html>",  # HTML payload
    ],
)
def test_insert_corrupt_or_malformed_json_strings_fallback(mock_pool_cls, mock_pg_pool, corrupt_input):
    """
    Adversarial 3.1: Proves any malformed or corrupted JSON string gracefully falls back
    to default taxonomy ('Unknown', [], {}) without raising unhandled exceptions.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    insert_video_analytics("corrupt_video.mp4", corrupt_input)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]

    assert params[0] == "corrupt_video.mp4"
    assert params[2] == "Unknown"
    assert params[3] == "Unknown"
    assert params[4].adapted == []
    assert params[5].adapted == {}


@patch("database_sink.pool.ThreadedConnectionPool")
@pytest.mark.parametrize(
    "non_dict_str_json, expected_type",
    [
        (json.dumps(["Item 1", "Item 2", "Item 3"]), "list"),  # Top-level list: "[...]"
        (json.dumps(123456), "int"),  # Top-level integer: "123456"
        (json.dumps(99.99), "float"),  # Top-level float: "99.99"
        (json.dumps(True), "bool"),  # Top-level boolean: "true"
        (json.dumps(None), "NoneType"),  # Top-level null: "null"
        (json.dumps("plain string inside json"), "str"),  # Top-level string: "\"plain string...\""
        ("NaN", "float"),  # Special float token in Python json
    ],
)
def test_insert_top_level_non_dict_json_strings_defect_probe(mock_pool_cls, mock_pg_pool, non_dict_str_json, expected_type):
    """
    Adversarial 3.2: Hardened Verification on Top-Level Non-Dict JSON Strings.
    In database_sink.py, json.loads() succeeds for top-level non-dict JSON types,
    and isinstance(parsed, dict) ensures safe fallback to {} without raising AttributeError.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    insert_video_analytics("non_dict_json_test.mp4", non_dict_str_json)
    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]
    assert params[0] == "non_dict_json_test.mp4"
    assert params[2] == "Unknown"
    assert params[3] == "Unknown"
    assert isinstance(params[4], Json)
    assert params[4].adapted == []
    assert isinstance(params[5], Json)
    assert params[5].adapted == {}


@patch("database_sink.pool.ThreadedConnectionPool")
@pytest.mark.parametrize(
    "raw_non_dict_obj",
    [
        ["list", "of", "items"],
        12345,
        99.99,
        True,
        False,
        None,
        ("tuple", "items"),
        {"set", "items"},
    ],
)
def test_insert_raw_non_dict_python_objects(mock_pool_cls, mock_pg_pool, raw_non_dict_obj):
    """
    Adversarial 3.3: Direct non-dict Python objects passed to tags_json.
    Verifies lines 208-210 handle non-dict objects gracefully.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    insert_video_analytics("raw_obj_test.mp4", raw_non_dict_obj)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]
    assert params[0] == "raw_obj_test.mp4"
    assert params[2] == "Unknown"
    assert params[3] == "Unknown"
    assert params[4].adapted == []
    assert params[5].adapted == {}


@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_internal_fields_with_anomalous_types(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 3.4: Internal dictionary fields containing unexpected types
    (e.g., domain=123, entity=True, viral_features='not_a_list', technical=['not_a_dict']).
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    anomalous_payload = {
        "domain": 12345,  # int instead of str
        "entity": True,  # bool instead of str
        "viral_features": "Single_String_Feature",  # str instead of list
        "technical": ["resolution: 4K", "fps: 60"],  # list instead of dict
    }

    insert_video_analytics("anomalous_fields.mp4", anomalous_payload)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]

    assert params[2] == "12345"
    assert params[3] == "True"
    assert params[4].adapted == []  # Non-list falls back to []
    assert params[5].adapted == {}  # Non-dict falls back to {}


# =============================================================================
# SUITE 4: EXTREME NUMERICAL VALUES & TIMESTAMPS
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
def test_insert_extreme_timestamps_and_numbers(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 4.1: Payloads containing extreme boundary numbers and timestamps.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    payload = {
        "domain": "Sports Cards",
        "entity": "1952 Topps Mickey Mantle PSA 10",
        "viral_features": [
            "Price_Record_$12,600,000",
            "Auction_Timestamp_2099-12-31T23:59:59.999999Z",
            "Epoch_Zero_1970-01-01T00:00:00Z",
        ],
        "technical": {
            "max_int64": 9223372036854775807,
            "min_int64": -9223372036854775808,
            "huge_int": 10**24,
            "small_float": 1e-15,
            "large_float": 1.79e308,
            "zero": 0,
            "negative_zero": -0.0,
            "gps_latitude": 36.114647123456789,
            "gps_longitude": -115.172813987654321,
            "sub_millisecond_timestamp": "2026-08-27T03:27:57.987654321+00:00",
        },
    }

    insert_video_analytics("mickey_mantle_record.mp4", payload)

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]

    tech = params[5].adapted
    assert tech["max_int64"] == 9223372036854775807
    assert tech["huge_int"] == 10**24
    assert tech["gps_latitude"] == 36.114647123456789


# =============================================================================
# SUITE 5: WINDOWS FILEPATH BOUNDARIES & UPSERT CONFLICT INTEGRITY
# =============================================================================

@patch("database_sink.pool.ThreadedConnectionPool")
@pytest.mark.parametrize(
    "complex_win_path, expected_filename",
    [
        (
            r"C:\Users\noahp\Downloads\Quick Share\20260819_212636.mp4",
            "20260819_212636.mp4",
        ),
        (
            r"C:\Media\EDM Sets\Subtronics & Excision @ Lost Lands [4K 60fps] #1.mp4",
            "Subtronics & Excision @ Lost Lands [4K 60fps] #1.mp4",
        ),
        (
            r"\\SERVER01\Share\Media\Ingest (Raw)\clip_final_and_test_(100%).mov",
            "clip_final_and_test_(100%).mov",
        ),
        (
            r"G:\My Drive\GOOGLE ANTIGRAVITY\photos\🔥_tokyo_東京_🗼.mp4",
            "🔥_tokyo_東京_🗼.mp4",
        ),
        (
            "relative/posix/path/to/video.mp4",
            "video.mp4",
        ),
    ],
)
def test_insert_complex_windows_filepaths_and_special_chars(
    mock_pool_cls, mock_pg_pool, complex_win_path, expected_filename
):
    """
    Adversarial 5.1: Pathlib parsing of complex Windows backslashes, UNC network shares,
    spaces, brackets, ampersands, and emojis.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    insert_video_analytics(complex_win_path, {"domain": "EDM", "entity": "Excision"})

    assert mock_cur.execute.called
    _, params = mock_cur.execute.call_args[0]

    assert params[0] == expected_filename
    assert params[1] == complex_win_path


@patch("database_sink.pool.ThreadedConnectionPool")
def test_upsert_conflict_clause_structure_and_parameter_mapping(mock_pool_cls, mock_pg_pool):
    """
    Adversarial 5.2: Verifies PostgreSQL ON CONFLICT (filename) DO UPDATE query mapping
    guarantees idempotent overwrites for duplicate filenames with updated taxonomy.
    """
    mock_pool_cls.return_value = mock_pg_pool["pool"]
    mock_cur = mock_pg_pool["cur"]

    # Initial Insert
    insert_video_analytics(
        "C:/Ingest/duplicate_clip.mp4",
        {
            "domain": "EDM",
            "entity": "Subtronics",
            "viral_features": ["Initial_Drop"],
            "technical": {"pass": 1},
        },
    )

    sql_1, params_1 = mock_cur.execute.call_args[0]
    assert params_1[0] == "duplicate_clip.mp4"
    assert params_1[2] == "EDM"
    assert params_1[3] == "Subtronics"
    assert params_1[4].adapted == ["Initial_Drop"]

    # Upsert with new taxonomy for same filename
    insert_video_analytics(
        "C:/Updated_Path/duplicate_clip.mp4",
        {
            "domain": "Sports Cards",
            "entity": "Luka Doncic",
            "viral_features": ["Updated_Rookie_Auto"],
            "technical": {"pass": 2},
        },
    )

    sql_2, params_2 = mock_cur.execute.call_args[0]
    assert "ON CONFLICT (filename) DO UPDATE SET" in sql_2
    assert "filepath = EXCLUDED.filepath" in sql_2
    assert "domain = EXCLUDED.domain" in sql_2
    assert "entity = EXCLUDED.entity" in sql_2
    assert "viral_features = EXCLUDED.viral_features" in sql_2
    assert "technical = EXCLUDED.technical" in sql_2
    assert "updated_at = CURRENT_TIMESTAMP" in sql_2

    assert params_2[0] == "duplicate_clip.mp4"
    assert params_2[1] == "C:/Updated_Path/duplicate_clip.mp4"
    assert params_2[2] == "Sports Cards"
    assert params_2[3] == "Luka Doncic"
    assert params_2[4].adapted == ["Updated_Rookie_Auto"]
    assert params_2[5].adapted == {"pass": 2}


# =============================================================================
# SUITE 6: STRICT CONTRACT ENFORCEMENT - HARDENED RESILIENCE VERIFICATION
# =============================================================================

def test_demonstrate_top_level_non_dict_json_string_hardened_success():
    """
    Adversarial 6.1 (Hardened Resilience Verification):
    Explicitly asserts that passing a valid top-level JSON array string (e.g. '["laser_1"]')
    safely and cleanly falls back to default taxonomy ({}) without raising AttributeError.
    """
    raw_json_array_str = '["Laser_Burst", "Bass_Drop"]'

    with patch("database_sink.pool.ThreadedConnectionPool") as mock_pool_cls:
        mock_pool = MagicMock()
        mock_pool.closed = False
        mock_conn = MagicMock()
        mock_cur = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cur
        mock_pool.getconn.return_value = mock_conn
        mock_pool_cls.return_value = mock_pool

        # Clean execution with safe fallback
        insert_video_analytics("sample_clip.mp4", raw_json_array_str)

        assert mock_cur.execute.called
        sql, params = mock_cur.execute.call_args[0]
        assert params[0] == "sample_clip.mp4"
        assert params[2] == "Unknown"
        assert params[3] == "Unknown"
        assert params[4].adapted == []
        assert params[5].adapted == {}
