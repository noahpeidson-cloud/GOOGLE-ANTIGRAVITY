"""
tests/test_adversarial_m2_scraper.py - Comprehensive Adversarial Stress Test Suite for Checklist Scraper Pipeline.
Authored by Teamwork Preview Challenger (Agent Challenger M2_2).

Target: sports_cards/ecosystem_hub/scraper_ingest.py, models.py, database.py.
Test Dimensions:
1. Malformed, truncated, corrupted, and deeply nested HTML documents.
2. Extreme card numbers ('00001', '04', 'NNO', 'RC-99', special unicode characters in player names).
3. Parallel combinatorial expansion (100 cards x 10 parallels = 1,000 cards with batch chunking and circuit breaker handling).
4. Database persistence and verification that leading zeroes are preserved in SQLite and Pandas queries.
5. Parser crash resistance and exact string formatting preservation.
6. Remote fetch network fault injection & offline fixture fallback.
7. SQL Injection and XSS payload resistance.
"""

from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd
from pydantic import ValidationError

# Ensure ecosystem_hub is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    AIStatus,
    CardCategory,
    CardExtractionSchema,
    CardRecord,
    VALID_CATEGORIES,
    CATEGORY_MAP,
    format_notes,
    synthesize_query,
)
from database import (
    CIRCUIT_BREAKER_BATCH_LIMIT,
    init_db,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    get_card_count,
    check_circuit_breaker,
    get_db_connection,
    update_card,
)
from scraper_ingest import (
    ChecklistCard,
    ChecklistHTMLParser,
    ChecklistMetadata,
    expand_checklist_parallels,
    expand_parallels,
    extract_parallels_from_html,
    fetch_and_parse_checklist,
    fetch_checklist_url,
    infer_metadata_from_text,
    ingest_checklist_to_database,
    ingest_scraper_cards,
    insert_scraped_checklist_to_db,
    parse_checklist_html,
    parse_checklist_line,
    parse_checklist_table_row,
    scrape_checklist_url,
)

SAMPLE_FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "..", "fixtures", "beckett_sample.html")


@pytest.fixture
def temp_db(tmp_path):
    """Provides a clean isolated SQLite database."""
    db_file = str(tmp_path / "test_adversarial_scraper.db")
    init_db(db_file)
    return db_file


# ===========================================================================
# DIMENSION 1: Malformed, Truncated, Corrupted, Deeply Nested HTML Documents
# ===========================================================================

class TestHTMLMalformedFuzzing:
    """Stress tests HTML parsing against corrupted, malformed, and adversarial inputs."""

    def test_empty_and_whitespace_html_returns_empty_list(self):
        """Parser never crashes on empty, whitespace, or newline-only HTML."""
        assert parse_checklist_html("") == []
        assert parse_checklist_html("   ") == []
        assert parse_checklist_html("\n\t\r\n") == []
        assert parse_checklist_html(None) == []

    def test_null_bytes_and_binary_garbage_resilience(self):
        """Parser survives null bytes and non-printable binary garbage."""
        garbage_inputs = [
            "<html>\x00\x01\x02<body><table><tr><td>01</td><td>Luka</td></tr></table></body></html>",
            "\x00" * 100 + "<table><tr><td>007</td><td>Bond</td></tr></table>",
            "Garbage \xff\xfe\xfd not valid html but has <table><tr><td>05</td><td>Player</td></tr></table>",
        ]
        for inp in garbage_inputs:
            cards = parse_checklist_html(inp, set_name="Test Set", year="2024", category="Basketball")
            assert isinstance(cards, list)
            assert len(cards) == 1
            assert cards[0].player in ("Luka", "Bond", "Player")

    def test_deeply_nested_html_tags_stress(self):
        """Parser survives 300 levels of nested div/section tags without recursion or memory errors."""
        nested_open = "".join(f"<div id='nest_{i}'><section class='sec_{i}'>" for i in range(150))
        table = """
        <table>
          <thead><tr><th>Card #</th><th>Player</th><th>Team</th></tr></thead>
          <tbody>
            <tr><td>01</td><td>Victor Wembanyama</td><td>Spurs</td></tr>
            <tr><td>02</td><td>Scoot Henderson</td><td>Blazers</td></tr>
          </tbody>
        </table>
        """
        nested_close = "".join("</section></div>" for _ in range(150))
        html = f"<html><body>{nested_open}{table}{nested_close}</body></html>"

        cards = parse_checklist_html(html, set_name="Nested Set", year="2023", category="Basketball")
        assert len(cards) == 2
        assert cards[0].card_number == "01"
        assert cards[0].player == "Victor Wembanyama"
        assert cards[1].card_number == "02"
        assert cards[1].player == "Scoot Henderson"

    def test_unclosed_tags_and_streaming_recovery(self):
        """Parser gracefully recovers from unclosed table, row, cell, and list tags."""
        unclosed_html = """
        <h1>2023-24 Prizm Basketball
        <table>
        <tr><td>01<td>Victor Wembanyama RC<td>Spurs
        <tr><td>02<td>Scoot Henderson<td>Blazers
        <tr><td>03<td>Brandon Miller<td>Hornets
        """
        cards = parse_checklist_html(unclosed_html)
        assert len(cards) >= 3
        card_nums = [c.card_number for c in cards]
        assert "01" in card_nums
        assert "02" in card_nums
        assert "03" in card_nums

    def test_truncated_html_mid_tag(self):
        """Parser does not crash when HTML is abruptly cut off mid-tag or mid-attribute."""
        truncated_cases = [
            "<table class='checklist'><tr><td>01</td><td>Victor Wembanyama</td><td>Sp",
            "<html><head><title>2024 Topps Baseball</title></head><body><table cla",
            "<ul><li>01 Victor Wembanyama - San Antonio Spurs</li><li>02 Scoot Hen",
            "<table",
            "<tr",
            "<td",
        ]
        for trunc in truncated_cases:
            res = parse_checklist_html(trunc)
            assert isinstance(res, list)

    def test_script_style_comment_traps(self):
        """Parser ignores pseudo-HTML tables embedded inside script, style, and comments."""
        trapped_html = """
        <html>
        <head>
          <style>
            table.fake { color: red; }
            /* <tr><td>999</td><td>Fake Style Player</td><td>Fake Team</td></tr> */
          </style>
          <script>
            var fakeData = "<table><tr><td>888</td><td>Fake JS Player</td><td>Team</td></tr></table>";
          </script>
        </head>
        <body>
          <!-- <table><tr><td>777</td><td>Fake Comment Player</td><td>Team</td></tr></table> -->
          <h1>2024 Panini Prizm Basketball Checklist</h1>
          <table>
            <tr><td>01</td><td>Real Player</td><td>Real Team</td></tr>
          </table>
        </body>
        </html>
        """
        cards = parse_checklist_html(trapped_html)
        players = [c.player for c in cards]
        assert "Real Player" in players
        assert "Fake Style Player" not in players
        assert "Fake JS Player" not in players
        assert "Fake Comment Player" not in players

    def test_large_html_document_stress(self):
        """Parser handles a massive 500-row HTML document with speed and integrity."""
        rows = "\n".join(f"<tr><td>{i:04d}</td><td>Player {i}</td><td>Team {i % 30}</td></tr>" for i in range(1, 501))
        large_html = f"""
        <html>
        <head><title>2024 Massive Checklist Basketball</title></head>
        <body>
          <h1>2024 Massive Checklist Basketball</h1>
          <table>
            <thead><tr><th>#</th><th>Player</th><th>Team</th></tr></thead>
            <tbody>
              {rows}
            </tbody>
          </table>
        </body>
        </html>
        """
        cards = parse_checklist_html(large_html, parallels=["Base"])
        assert len(cards) == 500
        assert cards[0].card_number == "0001"
        assert cards[0].player == "Player 1"
        assert cards[499].card_number == "0500"
        assert cards[499].player == "Player 500"

    def test_html_entity_unescaping_resilience(self):
        """Parser handles complex nested HTML entity references and quotes cleanly."""
        entity_html = """
        <table>
          <tr><td>01</td><td>Luka Don&#269;i&#263; &amp; Nikola Joki&#263;</td><td>Dallas &amp; Denver</td></tr>
          <tr><td>02</td><td>Ronald Acu&ntilde;a Jr. &quot;The Phenom&quot;</td><td>Atlanta Braves</td></tr>
          <tr><td>03</td><td>Shohei Ohtani &#8212; MVP &lt;Special&gt;</td><td>LA Dodgers</td></tr>
        </table>
        """
        cards = parse_checklist_html(entity_html, set_name="Entity Set", year="2024", category="Baseball")
        assert len(cards) == 3
        assert cards[0].player == "Luka Dončić & Nikola Jokić"
        assert cards[0].notes == "Dallas & Denver"
        assert cards[1].player == 'Ronald Acuña Jr. "The Phenom"'
        assert cards[2].player == "Shohei Ohtani — MVP <Special>"


# ===========================================================================
# DIMENSION 2: Extreme Card Numbers & Special Unicode Characters
# ===========================================================================

class TestExtremeCardNumbersAndUnicode:
    """Stress tests exact string preservation of leading zeroes, alphanumeric symbols, and unicode."""

    @pytest.mark.parametrize("card_num_input", [
        "00001", "00042", "007", "04", "00", "00000", "012345"
    ])
    def test_leading_zeroes_preserved_in_table_parsing(self, card_num_input):
        """Card numbers with leading zeros are strictly kept as strings without numeric truncation."""
        row = [card_num_input, "Victor Wembanyama", "San Antonio Spurs"]
        parsed = parse_checklist_table_row(row)
        assert parsed is not None
        assert parsed.card_number == card_num_input
        assert isinstance(parsed.card_number, str)

        expanded = expand_parallels([parsed], parallels=["Base"], default_year="2023", default_set="Prizm", default_category="Basketball")
        assert expanded[0].card_number == card_num_input
        assert isinstance(expanded[0].card_number, str)

    @pytest.mark.parametrize("line_input, expected_num", [
        ("00001 Victor Wembanyama - Spurs", "00001"),
        ("04 Charizard - Base Set", "04"),
        ("007 Luka Doncic - Mavericks", "007"),
        ("#0042 Stephen Curry - Warriors", "0042"),
        ("RC-99 Brandon Miller RC - Hornets", "RC-99"),
        ("NNO Ken Griffey Jr. - Mariners", "NNO"),
        ("SP-1 Shohei Ohtani - Dodgers", "SP-1"),
        ("04/102 Blastoise - Pokemon", "04/102"),
        ("1/1 Patrick Mahomes - Chiefs", "1/1"),
        ("PP-01 LeBron James - Lakers", "PP-01"),
    ])
    def test_extreme_card_number_formats_in_list_parsing(self, line_input, expected_num):
        """Parser extracts diverse non-standard and zero-padded card numbers from text lines."""
        card = parse_checklist_line(line_input)
        assert card is not None
        assert card.card_number == expected_num
        assert isinstance(card.card_number, str)

    @pytest.mark.parametrize("player_input, expected_clean, expected_rc", [
        ("Victor Wembanyama RC", "Victor Wembanyama", True),
        ("Scoot Henderson (RC)", "Scoot Henderson", True),
        ("Brandon Miller [RC]", "Brandon Miller", True),
        ("Amen Thompson Rookie", "Amen Thompson", True),
        ("Ausar Thompson (Rookie)", "Ausar Thompson", True),
        ("Stephen Curry", "Stephen Curry", False),
        ("Luka Dončić", "Luka Dončić", False),
        ("Ronald Acuña Jr.", "Ronald Acuña Jr.", False),
        ("Shohei Ohtani (大谷 翔平)", "Shohei Ohtani (大谷 翔平)", False),
    ])
    def test_rookie_flag_extraction_and_player_name_cleanliness(self, player_input, expected_clean, expected_rc):
        """Rookie indicators are flagged without corrupting valid diacritics or Japanese kanji."""
        row = ["01", player_input, "Test Team"]
        card = parse_checklist_table_row(row)
        assert card is not None
        assert card.player == expected_clean
        assert card.is_rookie == expected_rc


# ===========================================================================
# DIMENSION 3: Parallel Combinatorial Expansion Engine
# ===========================================================================

class TestParallelCombinatorialExpansion:
    """Stress tests massive combinatorial expansion across base checklist cards and parallel tiers."""

    def test_expansion_100_cards_by_10_parallels(self):
        """100 base cards expanded across 10 parallels yields exactly 1,000 distinct CardExtractionSchema items."""
        base_cards = [
            ChecklistCard(card_number=f"{i:04d}", player=f"Player {i}", team=f"Team {i % 30}")
            for i in range(1, 101)
        ]
        parallels = [
            "Base",
            "Silver Prizm",
            "Red Prizm /299",
            "Blue Prizm /199",
            "Purple Ice /149",
            "Green Prizm /99",
            "Orange Wave /25",
            "Gold Prizm /10",
            "Black Gold /5",
            "Nebula 1/1",
        ]
        expanded = expand_parallels(
            base_cards,
            parallels=parallels,
            default_year="2023",
            default_set="Panini Prizm",
            default_category="Basketball"
        )
        assert len(expanded) == 1000

        # Check Base cards: variation is empty, ai_status is CLEARED
        base_results = [c for c in expanded if c.variation == ""]
        assert len(base_results) == 100
        for b in base_results:
            assert b.ai_status == AIStatus.CLEARED.value
            assert b.year == "2023"
            assert b.set_name == "Panini Prizm"

        # Check each parallel: variation is non-empty, ai_status is REVIEW VARIATION
        for p in parallels[1:]:
            p_cards = [c for c in expanded if c.variation == p]
            assert len(p_cards) == 100
            for pc in p_cards:
                assert pc.ai_status == AIStatus.REVIEW_VARIATION.value
                assert pc.variation == p

        # Check leading zero preservation in 1000 expanded items
        assert expanded[0].card_number == "0001"
        assert expanded[9].card_number == "0001"
        assert expanded[10].card_number == "0002"

    def test_expansion_with_case_insensitive_base_variants(self):
        """Variations named 'base', 'Base', 'BASE', 'Base Set', '' normalize to empty variation and CLEARED status."""
        card = ChecklistCard(card_number="01", player="Wemby", team="Spurs")
        for base_name in ["", "Base", "base", "BASE", "Base Set", "base set", "  Base  "]:
            expanded = expand_parallels([card], parallels=[base_name], default_year="2023", default_set="Prizm", default_category="Basketball")
            assert len(expanded) == 1
            assert expanded[0].variation == ""
            assert expanded[0].ai_status == AIStatus.CLEARED.value

    def test_expansion_with_dictionary_and_schema_inputs(self):
        """expand_parallels accepts ChecklistCard, CardExtractionSchema, or raw dicts polymorphically."""
        items = [
            ChecklistCard(card_number="01", player="P1", team="T1"),
            CardExtractionSchema(player="P2", year="2022", set_name="Topps", card_number="007", category=CardCategory.BASEBALL),
            {"card_number": "0099", "player": "P3", "year": "2021", "set_name": "Optic", "category": "Football", "notes": "Chiefs"},
        ]
        expanded = expand_parallels(items, parallels=["Base", "Gold /10"])
        assert len(expanded) == 6
        assert expanded[0].card_number == "01"
        assert expanded[2].card_number == "007"
        assert expanded[4].card_number == "0099"


# ===========================================================================
# DIMENSION 4: Database Persistence, Batch Chunking & Circuit Breaker
# ===========================================================================

class TestDatabaseIngestionAndChunkingCircuitBreaker:
    """Stress tests batch chunking, circuit breaker handling, and sequential parent-child notes."""

    def test_batch_chunking_1000_cards_ingest(self, temp_db):
        """Ingests 1,000 cards in 500-card chunks without loss and with correct sequential notes."""
        cards = [
            CardExtractionSchema(
                player=f"Player {i}",
                year="2023",
                set_name="Panini Prizm",
                variation="" if i % 2 == 0 else "Silver Prizm",
                card_number=f"{i:04d}",
                category=CardCategory.BASKETBALL,
                condition="Raw",
                ai_status=AIStatus.CLEARED if i % 2 == 0 else AIStatus.REVIEW_VARIATION,
            )
            for i in range(1, 1001)
        ]
        # Ingest under parent ID 9000
        inserted_ids = ingest_scraper_cards(cards, parent_id=9000, db_path=temp_db, chunk_size=250)
        assert len(inserted_ids) == 1000
        assert get_card_count(temp_db) == 1000

        # Verify parent-child notes start at 9000-101 and continue through 9000-1100
        first_card = get_card_by_id(inserted_ids[0], db_path=temp_db)
        last_card = get_card_by_id(inserted_ids[999], db_path=temp_db)
        assert first_card["notes"] == "9000-101"
        assert last_card["notes"] == "9000-1100"

    def test_subsequent_batch_ingest_monotonic_child_ids(self, temp_db):
        """Subsequent batch under same parent ID seamlessly increments child IDs from previous maximum."""
        batch1 = [
            CardExtractionSchema(player=f"Batch1 Player {i}", year="2024", set_name="Set A", card_number=f"{i:02d}", category=CardCategory.BASKETBALL)
            for i in range(1, 11)
        ]
        ids1 = ingest_scraper_cards(batch1, parent_id=8800, db_path=temp_db)
        assert len(ids1) == 10
        last_b1 = get_card_by_id(ids1[-1], db_path=temp_db)
        assert last_b1["notes"] == "8800-110"

        batch2 = [
            CardExtractionSchema(player=f"Batch2 Player {i}", year="2024", set_name="Set A", card_number=f"{i:02d}", category=CardCategory.BASKETBALL)
            for i in range(11, 21)
        ]
        ids2 = ingest_scraper_cards(batch2, parent_id=8800, db_path=temp_db)
        assert len(ids2) == 10
        first_b2 = get_card_by_id(ids2[0], db_path=temp_db)
        last_b2 = get_card_by_id(ids2[-1], db_path=temp_db)
        assert first_b2["notes"] == "8800-111"
        assert last_b2["notes"] == "8800-120"

    def test_circuit_breaker_detection_at_scale(self, temp_db):
        """check_circuit_breaker correctly flags tripped state when cards >= 500."""
        # Under threshold (499 cards)
        cards_499 = [
            CardExtractionSchema(player=f"P {i}", year="2024", set_name="Set", card_number=f"{i}", category=CardCategory.BASKETBALL)
            for i in range(499)
        ]
        ingest_scraper_cards(cards_499, db_path=temp_db)
        status = check_circuit_breaker(temp_db, threshold=500)
        assert status["total_staged"] == 499
        assert status["circuit_breaker_tripped"] is False

        # At threshold (500 cards)
        cards_1 = [CardExtractionSchema(player="P 500", year="2024", set_name="Set", card_number="500", category=CardCategory.BASKETBALL)]
        ingest_scraper_cards(cards_1, db_path=temp_db)
        status = check_circuit_breaker(temp_db, threshold=500)
        assert status["total_staged"] == 500
        assert status["circuit_breaker_tripped"] is True

        # Over threshold (1000 cards)
        cards_500 = [
            CardExtractionSchema(player=f"P {i}", year="2024", set_name="Set", card_number=f"{i}", category=CardCategory.BASKETBALL)
            for i in range(501, 1001)
        ]
        ingest_scraper_cards(cards_500, db_path=temp_db)
        status = check_circuit_breaker(temp_db, threshold=500)
        assert status["total_staged"] == 1000
        assert status["circuit_breaker_tripped"] is True


# ===========================================================================
# DIMENSION 5: SQLite & Pandas Type Stability & Leading Zero Preservation
# ===========================================================================

class TestSQLiteAndPandasTypeStability:
    """Stress tests SQLite TEXT storage and Pandas DataFrame retrieval to ensure no leading zeroes are lost."""

    def test_sqlite_column_type_and_leading_zeroes(self, temp_db):
        """SQLite strictly stores card_number as TEXT, preserving '00001', '04', '007'."""
        test_cards = [
            CardExtractionSchema(player="Player 1", year="2024", set_name="Set", card_number="00001", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Player 2", year="2024", set_name="Set", card_number="04", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Player 3", year="2024", set_name="Set", card_number="007", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Player 4", year="2024", set_name="Set", card_number="00000", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Player 5", year="2024", set_name="Set", card_number="NNO", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Player 6", year="2024", set_name="Set", card_number="RC-99", category=CardCategory.BASKETBALL),
        ]
        ids = ingest_scraper_cards(test_cards, db_path=temp_db)
        assert len(ids) == 6

        # Direct raw SQLite query inspection
        with get_db_connection(temp_db) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, card_number, typeof(card_number) FROM cards ORDER BY id ASC;")
            rows = cursor.fetchall()

        expected_numbers = ["00001", "04", "007", "00000", "NNO", "RC-99"]
        for idx, row in enumerate(rows):
            assert row["card_number"] == expected_numbers[idx]
            assert row[2] == "text"
            assert isinstance(row["card_number"], str)

    def test_pandas_read_sql_query_type_stability(self, temp_db):
        """Pandas DataFrame query preserves string data type and leading zeroes."""
        test_cards = [
            CardExtractionSchema(player="Victor Wembanyama", year="2023", set_name="Prizm", card_number="00001", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Scoot Henderson", year="2023", set_name="Prizm", card_number="007", category=CardCategory.BASKETBALL),
            CardExtractionSchema(player="Brandon Miller", year="2023", set_name="Prizm", card_number="04", category=CardCategory.BASKETBALL),
        ]
        ingest_scraper_cards(test_cards, db_path=temp_db)

        # Standard Pandas SQL extraction
        with get_db_connection(temp_db) as conn:
            df = pd.read_sql_query("SELECT id, player, card_number FROM cards ORDER BY id ASC;", conn, dtype={"card_number": str})

        assert len(df) == 3
        card_numbers = df["card_number"].tolist()
        assert card_numbers == ["00001", "007", "04"]
        assert all(isinstance(val, str) for val in card_numbers)
        assert card_numbers[0] != "1"
        assert card_numbers[1] != "7"
        assert card_numbers[2] != "4"

    def test_update_card_preserves_leading_zeroes(self, temp_db):
        """Updating investment or status does not cast or truncate card_number."""
        card = CardExtractionSchema(player="Luka Doncic", year="2024", set_name="Prizm", card_number="00077", category=CardCategory.BASKETBALL)
        card_id = ingest_scraper_cards([card], db_path=temp_db)[0]

        # Update investment and ai_status
        success = update_card(card_id, {"investment": 150.0, "ai_status": AIStatus.CLEARED.value}, db_path=temp_db)
        assert success is True

        updated = get_card_by_id(card_id, db_path=temp_db)
        assert updated["card_number"] == "00077"
        assert isinstance(updated["card_number"], str)
        assert updated["investment"] == 150.0


# ===========================================================================
# DIMENSION 6: Remote Fetch, Network Fault Injection & Offline Fallback
# ===========================================================================

class TestRemoteFetchAndOfflineResilience:
    """Stress tests network requests, timeout handling, and offline fixture fallbacks."""

    def test_fetch_network_timeout_triggers_fallback(self):
        """Connection timeout transparently falls back to local HTML fixture without crash."""
        with patch("scraper_ingest.requests.get", side_effect=Exception("Connection timed out")):
            cards = fetch_and_parse_checklist(
                url="https://www.cardboardconnection.com/2023-24-panini-prizm",
                fallback_fixture_path=SAMPLE_FIXTURE_PATH,
                parallels=["Base"],
            )
            assert len(cards) >= 5
            assert cards[0].player == "Victor Wembanyama"
            assert cards[0].card_number == "01"

    def test_fetch_http_500_server_error_triggers_fallback(self):
        """HTTP 500 error falls back to local fixture."""
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("500 Internal Server Error")
        with patch("scraper_ingest.requests.get", return_value=mock_resp):
            cards = fetch_and_parse_checklist(
                url="https://www.beckett.com/error-set",
                fallback_fixture_path=SAMPLE_FIXTURE_PATH,
                parallels=["Base"],
            )
            assert len(cards) >= 5

    def test_fetch_missing_network_and_no_fallback_raises_runtime_error(self):
        """If network fails and fallback path is invalid, raises descriptive RuntimeError."""
        with patch("scraper_ingest.requests.get", side_effect=Exception("DNS resolution failed")):
            with pytest.raises(RuntimeError, match="Failed to fetch checklist"):
                fetch_and_parse_checklist(
                    url="https://invalid-non-existent-url-999.com/checklist",
                    fallback_fixture_path="non_existent_fixture.html",
                )

    def test_fetch_user_agent_header_present(self):
        """Requests to remote URLs pass modern Mozilla User-Agent header."""
        with patch("scraper_ingest.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = "<table><tr><td>01</td><td>Player</td><td>Team</td></tr></table>"
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            fetch_checklist_url("https://www.beckett.com/sample")
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert "headers" in call_kwargs
            assert "User-Agent" in call_kwargs["headers"]
            assert "Mozilla/5.0" in call_kwargs["headers"]["User-Agent"]


# ===========================================================================
# DIMENSION 7: Security, SQL Injection & XSS Immunity
# ===========================================================================

class TestSecurityAndInjectionImmunity:
    """Tests parameterized SQL execution and HTML sanitization."""

    @pytest.mark.parametrize("payload", [
        "Robert'); DROP TABLE cards;--",
        "' OR '1'='1",
        "admin'--",
        "1; WAITFOR DELAY '0:0:5'--",
        "Luka <script>alert(1)</script> Doncic",
        "Victor <b>Wembanyama</b>",
    ])
    def test_sql_and_html_injection_payloads_safely_persisted(self, payload, temp_db):
        """Malicious payloads in card fields are treated strictly as literal strings or stripped safely."""
        html = f"""
        <table>
          <tr><td>01</td><td>{payload}</td><td>Team {payload}</td></tr>
        </table>
        """
        cards = parse_checklist_html(html, set_name=f"Set {payload}", year="2024", category="Basketball")
        assert len(cards) >= 1
        ids = ingest_scraper_cards(cards, db_path=temp_db)
        assert len(ids) == len(cards)

        card = get_card_by_id(ids[0], db_path=temp_db)
        assert card is not None
        # Table must remain intact and contain exactly 1 card
        assert get_card_count(temp_db) == 1

    def test_empty_tag_only_cells_are_dropped(self):
        """Cells containing only void/empty tags (e.g. <img src=x>) without text are dropped safely."""
        html = """
        <table>
          <tr><td>01</td><td><img src=x onerror=alert(1)></td><td>Team</td></tr>
        </table>
        """
        cards = parse_checklist_html(html, set_name="Test Set", year="2024", category="Basketball")
        # Empty player cell is rejected, parser does not crash
        assert len(cards) == 0


# ===========================================================================
# DIMENSION 8: High-Scale Performance & Memory Bounds
# ===========================================================================

class TestHighScalePerformance:
    """Tests expansion and parsing under massive scale (20,000 cards in memory)."""

    def test_massive_expansion_20k_cards_speed(self):
        """Expanding 1,000 base cards across 20 parallels (20,000 cards) completes rapidly."""
        import time
        base_cards = [
            ChecklistCard(card_number=f"{i:04d}", player=f"Player {i}", team=f"Team {i % 30}")
            for i in range(1, 1001)
        ]
        parallels = [f"Parallel Tier {p}" for p in range(1, 21)]

        start = time.perf_counter()
        expanded = expand_parallels(base_cards, parallels=parallels, default_year="2024", default_set="Large Set", default_category="Basketball")
        duration = time.perf_counter() - start

        assert len(expanded) == 20000
        # Should complete in under 2.0 seconds in memory
        assert duration < 2.0
        assert expanded[0].card_number == "0001"
        assert expanded[-1].card_number == "1000"


# ===========================================================================
# DIMENSION 9: Randomized Mutation Fuzzing
# ===========================================================================

class TestRandomizedMutationFuzzing:
    """Fuzzes parser with randomized HTML strings and malformed tokens."""

    def test_random_mutation_fuzzing_never_crashes(self):
        """100 randomly generated corrupt HTML templates must never raise unhandled exceptions."""
        import random

        tags = ["<table>", "</table>", "<tr>", "</tr>", "<td>", "</td>", "<th>", "</th>", "<ul>", "</ul>", "<li>", "</li>", "<h1>", "</h1>", "<div>", "</div>"]
        tokens = ["01", "007", "00042", "RC-1", "NNO", "Luka", "Wemby", "Spurs", "Mavericks", "<script>", "&amp;", "<!--", "-->", "\x00", "\n", "\t", '"', "'"]

        for seed in range(100):
            random.seed(seed)
            parts = []
            for _ in range(30):
                if random.random() < 0.5:
                    parts.append(random.choice(tags))
                else:
                    parts.append(random.choice(tokens))
            fuzz_html = "".join(parts)

            # Parser must never throw exception
            result = parse_checklist_html(fuzz_html)
            assert isinstance(result, list)


# ===========================================================================
# DIMENSION 10: Category & Year Metadata Inference
# ===========================================================================

class TestMetadataInference:
    """Tests metadata inference across all sports and trading card categories."""

    @pytest.mark.parametrize("category_name", sorted(VALID_CATEGORIES))
    def test_all_22_categories_inferred_correctly(self, category_name):
        """Heading with category name correctly resolves to exact canonical CardCategory."""
        heading = f"2023-24 Panini Prizm {category_name} Checklist Set Info"
        inferred = infer_metadata_from_text(heading)
        assert inferred["category"] == category_name
        assert inferred["year"] == "2023"

    @pytest.mark.parametrize("header_text, expected_year, expected_set", [
        ("2023-24 Panini Prizm Basketball Checklist", "2023", "Panini Prizm"),
        ("2020/21 Upper Deck Young Guns Hockey Cards", "2020", "Upper Deck Young Guns"),
        ("1996-97 Topps Chrome Basketball Complete Set", "1996", "Topps Chrome"),
        ("2024 Bowman Chrome Baseball Checklist", "2024", "Bowman Chrome"),
        ("1986 Fleer Basketball Base Set Checklist", "1986", "Fleer"),
    ])
    def test_multi_year_season_and_set_name_inference(self, header_text, expected_year, expected_set):
        """Multi-year seasons correctly extract primary 4-digit year and clean set name."""
        meta = infer_metadata_from_text(header_text)
        assert meta["year"] == expected_year
        assert meta["set_name"] == expected_set


