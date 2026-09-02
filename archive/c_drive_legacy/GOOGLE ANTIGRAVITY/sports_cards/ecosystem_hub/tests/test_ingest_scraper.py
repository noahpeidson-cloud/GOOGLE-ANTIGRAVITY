"""
tests/test_ingest_scraper.py - Comprehensive Test Suite for Checklist Scraper Ingest Pipeline.
Tests Beckett & Cardboard Connection HTML parsing, table/list extraction,
string card number preservation, rookie tag extraction, parallel variation expansion,
offline fallback, and SQLite database persistence.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure ecosystem_hub is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    AIStatus,
    CardCategory,
    CardExtractionSchema,
    CardRecord,
    VALID_CATEGORIES,
    format_notes,
    synthesize_query,
)
from database import (
    init_db,
    insert_card,
    get_card_by_id,
    get_all_cards,
    get_card_count,
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
def sample_html_content() -> str:
    """Reads static beckett_sample.html fixture."""
    with open(SAMPLE_FIXTURE_PATH, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated SQLite database for scraper tests."""
    db_file = str(tmp_path / "test_scraper_portfolio.db")
    init_db(db_file)
    return db_file


# ---------------------------------------------------------------------------
# Tier 1: HTML Parsing & Field Extraction
# ---------------------------------------------------------------------------

class TestChecklistHTMLParser:
    """Tests HTML parsing of tables, lists, and metadata."""

    def test_parse_beckett_table_structure(self, sample_html_content):
        cards = parse_checklist_html(sample_html_content, parallels=["Base"])
        assert len(cards) >= 5

        # Card # 01: Victor Wembanyama RC | San Antonio Spurs
        wemby = next(c for c in cards if c.card_number == "01")
        assert wemby.player == "Victor Wembanyama"
        assert wemby.card_number == "01"
        assert wemby.notes == "San Antonio Spurs"
        assert wemby.category == CardCategory.BASKETBALL.value
        assert wemby.year == "2023"
        assert wemby.ai_status == AIStatus.CLEARED.value

        # Card # 007: Luka Dončić | Dallas Mavericks
        luka = next(c for c in cards if c.card_number == "007")
        assert luka.player == "Luka Dončić"
        assert luka.card_number == "007"
        assert luka.notes == "Dallas Mavericks"

        # Card # RC-1: Brandon Miller RC | Charlotte Hornets
        miller = next(c for c in cards if c.card_number == "RC-1")
        assert miller.player == "Brandon Miller"
        assert miller.card_number == "RC-1"
        assert miller.notes == "Charlotte Hornets"

    def test_parse_cardboard_connection_list(self):
        list_html = """
        <html>
        <head><title>2022-23 Upper Deck Series 1 Hockey Checklist</title></head>
        <body>
          <h1>2022-23 Upper Deck Series 1 Hockey Checklist</h1>
          <h2>Young Guns Rookie Checklist</h2>
          <ul>
            <li>201 Matt Boldy RC - Minnesota Wild</li>
            <li>202 Matty Beniers RC - Seattle Kraken</li>
            <li>203 Owen Power (RC) - Buffalo Sabres</li>
            <li>005 Juraj Slafkovsky - Montreal Canadiens</li>
          </ul>
        </body>
        </html>
        """
        cards = parse_checklist_html(list_html, parallels=["Base"])
        assert len(cards) == 4
        boldy = cards[0]
        assert boldy.card_number == "201"
        assert boldy.player == "Matt Boldy"
        assert boldy.notes == "Minnesota Wild"
        assert boldy.category == CardCategory.HOCKEY.value

        juraj = cards[3]
        assert juraj.card_number == "005"
        assert juraj.player == "Juraj Slafkovsky"

    def test_parse_rookie_card_tag_detection(self):
        line1 = "01 Victor Wembanyama RC - San Antonio Spurs"
        card1 = parse_checklist_line(line1)
        assert card1 is not None
        assert card1.is_rookie is True
        assert card1.player == "Victor Wembanyama"
        assert card1.card_number == "01"

        line2 = "101 Scoot Henderson (RC) - Portland Trail Blazers"
        card2 = parse_checklist_line(line2)
        assert card2 is not None
        assert card2.is_rookie is True
        assert card2.player == "Scoot Henderson"

        line3 = "75 Stephen Curry - Golden State Warriors"
        card3 = parse_checklist_line(line3)
        assert card3 is not None
        assert card3.is_rookie is False
        assert card3.player == "Stephen Curry"

    def test_parse_leading_zeros_preservation(self):
        table_row = ["007", "James Bond RC", "MI6"]
        card = parse_checklist_table_row(table_row)
        assert card is not None
        assert card.card_number == "007"
        assert isinstance(card.card_number, str)

        table_row_frac = ["04/102", "Charizard", "Base Set"]
        card_frac = parse_checklist_table_row(table_row_frac)
        assert card_frac is not None
        assert card_frac.card_number == "04/102"

    def test_parse_malformed_html_graceful(self):
        malformed = "<div><table><tr><td>01<td>Incomplete Row<tr><td>02<td>Second Player<td>Team"
        cards = parse_checklist_html(malformed, set_name="Test Set", year="2024", category="Basketball")
        assert len(cards) >= 1

        empty = ""
        cards_empty = parse_checklist_html(empty)
        assert cards_empty == []

    def test_parse_html_entities_unescaped(self):
        row = ["01", "Luka Don&#269;i&#263; &amp; Nikola Joki&#263;", "Dallas &amp; Denver"]
        card = parse_checklist_table_row(row)
        assert card is not None
        assert "Dončić" in card.player
        assert "Jokić" in card.player
        assert "&" in card.player
        assert "&" in card.team


# ---------------------------------------------------------------------------
# Tier 2: Parallel Variation Expansion Engine
# ---------------------------------------------------------------------------

class TestParallelExpansion:
    """Tests expanding parsed base checklist cards across parallel sets."""

    def test_parallel_expansion_base_only(self):
        raw = [
            ChecklistCard(card_number="01", player="Victor Wembanyama", team="Spurs"),
            ChecklistCard(card_number="02", player="Scoot Henderson", team="Blazers"),
        ]
        expanded = expand_parallels(raw, parallels=["Base"], default_year="2023", default_set="Panini Prizm", default_category="Basketball")
        assert len(expanded) == 2
        for c in expanded:
            assert c.variation == ""
            assert c.ai_status == AIStatus.CLEARED.value

    def test_parallel_expansion_multiple(self):
        raw = [
            ChecklistCard(card_number="01", player="Victor Wembanyama", team="Spurs"),
            ChecklistCard(card_number="02", player="Scoot Henderson", team="Blazers"),
        ]
        parallels = ["Base", "Silver Prizm", "Red Prizm /99", "Gold Prizm /10"]
        expanded = expand_parallels(raw, parallels=parallels, default_year="2023", default_set="Panini Prizm", default_category="Basketball")
        # 2 cards * 4 parallels = 8 cards
        assert len(expanded) == 8

        base_wemby = expanded[0]
        assert base_wemby.variation == ""
        assert base_wemby.ai_status == AIStatus.CLEARED.value

        silver_wemby = expanded[1]
        assert silver_wemby.variation == "Silver Prizm"
        assert silver_wemby.ai_status == AIStatus.REVIEW_VARIATION.value

        gold_scoot = expanded[7]
        assert gold_scoot.variation == "Gold Prizm /10"
        assert gold_scoot.ai_status == AIStatus.REVIEW_VARIATION.value

    def test_extract_parallels_from_fixture_html(self, sample_html_content):
        parser = ChecklistHTMLParser()
        parser.feed(sample_html_content)
        parser.close()

        parallels = extract_parallels_from_html(parser)
        assert "Silver Prizm" in parallels
        assert "Red Prizm /99" in parallels
        assert "Gold Prizm /10" in parallels


# ---------------------------------------------------------------------------
# Tier 3: Database Ingestion Bridge
# ---------------------------------------------------------------------------

class TestScraperToDatabaseBridge:
    """Tests inserting parsed checklist cards directly into SQLite."""

    def test_ingest_checklist_html_to_db(self, sample_html_content, temp_db):
        cards = parse_checklist_html(sample_html_content, parallels=["Base"])
        ids = ingest_scraper_cards(cards, parent_id=8500, db_path=temp_db)

        assert len(ids) == len(cards)
        assert len(ids) >= 5

        first = get_card_by_id(ids[0], db_path=temp_db)
        assert first is not None
        assert first["notes"] == "8500-101"
        assert first["query"] == "2023 Panini Prizm Victor Wembanyama Raw"
        assert first["ai_status"] == AIStatus.CLEARED.value

    def test_ingest_checklist_with_parallels_to_db(self, sample_html_content, temp_db):
        cards = parse_checklist_html(
            sample_html_content,
            parallels=["Base", "Silver Prizm", "Gold Prizm /10"],
        )
        ids = insert_scraped_checklist_to_db(cards, parent_id=8600, db_path=temp_db)
        assert len(ids) == len(cards)

        db_cards = get_all_cards(db_path=temp_db, limit=500)
        silver_cards = [c for c in db_cards if c["variation"] == "Silver Prizm"]
        assert len(silver_cards) >= 5
        for sc in silver_cards:
            assert sc["ai_status"] == AIStatus.REVIEW_VARIATION.value
            assert "Silver Prizm" in sc["query"]

    def test_ingest_sequential_notes_and_subsequent_batches(self, sample_html_content, temp_db):
        batch1 = parse_checklist_html(sample_html_content, parallels=["Base"])[:3]
        ids1 = ingest_scraper_cards(batch1, parent_id=8700, db_path=temp_db)

        c1 = get_card_by_id(ids1[0], db_path=temp_db)
        c2 = get_card_by_id(ids1[1], db_path=temp_db)
        c3 = get_card_by_id(ids1[2], db_path=temp_db)
        assert c1["notes"] == "8700-101"
        assert c2["notes"] == "8700-102"
        assert c3["notes"] == "8700-103"

        # Subsequent batch under same parent ID 8700
        batch2 = parse_checklist_html(sample_html_content, parallels=["Base"])[3:5]
        ids2 = ingest_scraper_cards(batch2, parent_id=8700, db_path=temp_db)

        c4 = get_card_by_id(ids2[0], db_path=temp_db)
        c5 = get_card_by_id(ids2[1], db_path=temp_db)
        assert c4["notes"] == "8700-104"
        assert c5["notes"] == "8700-105"


# ---------------------------------------------------------------------------
# Tier 4: Remote Fetch & Offline Fallback Handling
# ---------------------------------------------------------------------------

class TestScraperOfflineAndErrors:
    """Tests network handling, mock requests, and offline fallback."""

    def test_fetch_and_parse_offline_fallback(self, sample_html_content):
        with patch("scraper_ingest.fetch_checklist_url", side_effect=Exception("Connection refused")):
            cards = fetch_and_parse_checklist(
                url="https://www.beckett.com/basketball/2023-24-panini-prizm",
                fallback_fixture_path=SAMPLE_FIXTURE_PATH,
                parallels=["Base"],
            )
            assert len(cards) >= 5
            assert cards[0].player == "Victor Wembanyama"

    def test_scrape_checklist_url_live_mock(self, sample_html_content):
        with patch("scraper_ingest.requests.get") as mock_get:
            mock_resp = MagicMock()
            mock_resp.text = sample_html_content
            mock_resp.raise_for_status.return_value = None
            mock_get.return_value = mock_resp

            cards = scrape_checklist_url(
                url="https://www.beckett.com/sample-set",
                parallels=["Base"],
            )
            assert len(cards) >= 5

    def test_scraper_category_normalization(self):
        meta1 = infer_metadata_from_text("2023 Panini Prizm Basketball Checklist")
        assert meta1["category"] == "Basketball"
        assert meta1["year"] == "2023"

        meta2 = infer_metadata_from_text("2021 Topps Chrome Formula 1 Racing Set Info")
        assert meta2["category"] == "Racing"
        assert meta2["year"] == "2021"

        meta3 = infer_metadata_from_text("2022 Panini Prizm UFC MMA Trading Cards")
        assert meta3["category"] == "UFC/MMA"
        assert meta3["year"] == "2022"

    def test_scraper_sql_injection_safety(self, temp_db):
        malicious_html = """
        <table>
          <tr><td>01</td><td>Robert'); DROP TABLE cards;--</td><td>Spurs</td></tr>
        </table>
        """
        cards = parse_checklist_html(malicious_html, set_name="Inject Set", year="2024", category="Basketball")
        ids = ingest_scraper_cards(cards, db_path=temp_db)
        assert len(ids) == 1

        saved = get_card_by_id(ids[0], db_path=temp_db)
        assert saved["player"] == "Robert'); DROP TABLE cards;--"
        # Ensure database table still exists and count is intact
        assert get_card_count(temp_db) == 1
