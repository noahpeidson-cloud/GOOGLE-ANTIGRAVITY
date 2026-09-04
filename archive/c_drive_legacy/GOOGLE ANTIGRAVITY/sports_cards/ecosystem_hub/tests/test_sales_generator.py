"""
test_sales_generator.py - Comprehensive Test Suite for Sales Listing Generator.
Validates SEO title bounds (<100 chars), anti-spam buzzword filtering, 6-section structure,
graded vs raw condition copy, 6-8 viral hashtags, Gemini SDK mocking, and database integration.
"""

import os
import tempfile
import sqlite3
import pytest
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from unittest.mock import MagicMock, patch

from models import CardRecord, CardCategory, AIStatus
from database import init_db, insert_card
from sales_generator import (
    sanitize_seo_title,
    build_seo_title,
    build_price_section,
    build_specifications_section,
    build_condition_section,
    build_shipping_pickup_section,
    build_hashtags,
    resolve_asking_price,
    normalize_card_input,
    MockSalesGenerator,
    generate_marketplace_listing,
    generate_listing_for_card_id,
    generate_batch_marketplace_listings,
    build_structured_listing,
)


@pytest.fixture
def sample_graded_card():
    return {
        "player": "Luka Doncic",
        "year": "2018",
        "set_name": "Panini Prizm",
        "variation": "Silver Prizm",
        "card_number": "280",
        "category": "Basketball",
        "condition": "PSA 10",
        "slab_serial_number": "48192041",
        "investment": 800.0,
        "estimated_value": 1450.0,
        "notes": "8492-105",
    }


@pytest.fixture
def sample_raw_card():
    return {
        "player": "Shohei Ohtani",
        "year": "2018",
        "set_name": "Topps Chrome",
        "variation": "Refractor",
        "card_number": "150",
        "category": "Baseball",
        "condition": "Raw",
        "slab_serial_number": "",
        "investment": 120.0,
        "estimated_value": 300.0,
        "notes": "8492-106",
    }


# ===========================================================================
# Tier 1: Input Normalization & Pricing Tests
# ===========================================================================

class TestNormalizationAndPricing:
    """Validates normalization from multiple input types and price resolution."""

    def test_normalize_from_dict(self, sample_graded_card):
        res = normalize_card_input(sample_graded_card)
        assert res["player"] == "Luka Doncic"
        assert res["investment"] == 800.0

    def test_normalize_from_card_record(self, sample_graded_card):
        rec = CardRecord(**sample_graded_card)
        res = normalize_card_input(rec)
        assert res["player"] == "Luka Doncic"
        assert res["condition"] == "PSA 10"

    def test_normalize_from_sqlite_row(self, sample_graded_card):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        card_id = insert_card(sample_graded_card, db_path=db_path)

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id = ?", (card_id,))
        row = cursor.fetchone()
        conn.close()

        res = normalize_card_input(row)
        assert res["player"] == "Luka Doncic"
        assert res["slab_serial_number"] == "48192041"

        if os.path.exists(db_path):
            os.remove(db_path)

    def test_resolve_asking_price_explicit(self, sample_graded_card):
        price = resolve_asking_price(sample_graded_card, asking_price=1600.0)
        assert price == 1600.0

    def test_resolve_asking_price_from_estimated_value(self, sample_graded_card):
        price = resolve_asking_price(sample_graded_card, asking_price=None)
        assert price == 1450.0

    def test_resolve_asking_price_from_investment(self, sample_graded_card):
        card = dict(sample_graded_card, estimated_value=0.0, investment=850.0)
        price = resolve_asking_price(card, asking_price=None)
        assert price == 850.0

    def test_resolve_asking_price_default(self, sample_graded_card):
        card = dict(sample_graded_card, estimated_value=0.0, investment=0.0)
        price = resolve_asking_price(card, asking_price=None)
        assert price == 50.0


# ===========================================================================
# Tier 2 & Tier 3: SEO Title Bounds & Buzzword Filtering
# ===========================================================================

class TestSEOTitleAndBuzzwords:
    """Validates < 100 character bounds and anti-spam buzzword removal."""

    def test_title_under_100_chars(self, sample_graded_card):
        title = build_seo_title(sample_graded_card)
        assert len(title) < 100
        assert "2018 Panini Prizm Luka Doncic Silver Prizm PSA 10" in title

    def test_buzzwords_removal(self):
        spammy_title = "2020 Panini Prizm L@@K INVEST ?? Luka Doncic PSA 10? RARE MOON ?? BUY NOW"
        clean = sanitize_seo_title(spammy_title)
        assert "L@@K" not in clean
        assert "INVEST" not in clean
        assert "FIRE" not in clean
        assert "PSA 10?" not in clean
        assert "RARE" not in clean
        assert "MOON" not in clean
        assert len(clean) < 100

    def test_extremely_long_title_truncation(self):
        long_card = {
            "player": "Victor Wembanyama Super Extended Name With Multiple Middle Names And Suffixes",
            "year": "2023",
            "set_name": "Panini National Treasures Collegiate Football Basketball Mega Edition",
            "variation": "Gold Vinyl Patch Autograph Booklet Parallel Serial Numbered /5",
            "condition": "BGS 9.5",
        }
        title = build_seo_title(long_card)
        assert len(title) < 100
        assert not title.endswith(" ")


# ===========================================================================
# Tier 4: Deterministic Mock Generator & Section Content
# ===========================================================================

class TestMockSalesGenerator:
    """Validates 6 mandatory sections, graded vs raw copy, and hashtags."""

    def test_all_6_sections_present(self, sample_graded_card):
        listing = MockSalesGenerator.generate(sample_graded_card)
        assert "ASKING PRICE:" in listing
        assert "KEY SPECIFICATIONS:" in listing
        assert "CONDITION & AUTHENTICITY:" in listing
        assert "SHIPPING & LOCAL PICKUP:" in listing
        assert "TAGS:" in listing

    def test_graded_card_copy_details(self, sample_graded_card):
        listing = MockSalesGenerator.generate(sample_graded_card)
        assert "PSA 10" in listing
        assert "48192041" in listing
        assert "encapsulated slab" in listing

    def test_raw_card_copy_disclaimer(self, sample_raw_card):
        listing = MockSalesGenerator.generate(sample_raw_card)
        assert "N/A (Raw)" in listing
        assert "Pack-fresh to near-mint/mint raw card" in listing
        assert "Card is in raw condition" in listing
        assert "Sold as-is" in listing

    def test_hashtags_between_6_and_8(self, sample_graded_card, sample_raw_card):
        tags1 = build_hashtags(sample_graded_card)
        assert 6 <= len(tags1) <= 8
        assert all(t.startswith("#") for t in tags1)

        tags2 = build_hashtags(sample_raw_card)
        assert 6 <= len(tags2) <= 8
        assert all(t.startswith("#") for t in tags2)

    def test_custom_notes_included(self, sample_graded_card):
        listing = MockSalesGenerator.generate(sample_graded_card, custom_notes="Will consider trade for LeBron rookie")
        assert "Additional Notes: Will consider trade for LeBron rookie" in listing

    def test_structured_listing_model(self, sample_graded_card):
        struct = build_structured_listing(sample_graded_card, asking_price=1500.0, card_id=42)
        assert struct.title == build_seo_title(sample_graded_card)
        assert struct.price == 1500.0
        assert struct.price_formatted == "$1,500.00"
        assert struct.card_id == 42
        assert 6 <= len(struct.hashtags) <= 8
        assert "Year" in struct.specs
        assert struct.specs["Slab Certification #"] == "48192041"


# ===========================================================================
# Tier 5: Gemini SDK Mocking & Fallback
# ===========================================================================

class TestGeminiIntegrationAndFallback:
    """Validates google.genai live mocking and offline resilience."""

    def test_explicit_mock_flag(self, sample_graded_card):
        listing = generate_marketplace_listing(sample_graded_card, mock=True)
        assert "ASKING PRICE" in listing
        assert "KEY SPECIFICATIONS" in listing

    def test_gemini_sdk_mock_invocation(self, sample_graded_card):
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = (
            "2018 Panini Prizm Luka Doncic PSA 10\n\n"
            "?? ASKING PRICE: $1,450.00\n"
            "? Payment Terms: Cash, Zelle, PayPal\n\n"
            "?? KEY SPECIFICATIONS:\n"
            "? Year: 2018\n? Brand / Set: Panini Prizm\n? Player: Luka Doncic\n\n"
            "?? CONDITION & AUTHENTICITY:\nOfficial PSA slab.\n\n"
            "?? SHIPPING & LOCAL PICKUP:\nSecure bubble mailer.\n\n"
            "??? TAGS:\n#SportsCards #TheHobby #BasketballCards #LukaDoncic #PaniniPrizm #PSA10"
        )
        mock_client.models.generate_content.return_value = mock_response

        listing = generate_marketplace_listing(
            sample_graded_card,
            mock=False,
            api_key="test_api_key_12345",
            client=mock_client
        )
        assert "Luka Doncic" in listing
        assert mock_client.models.generate_content.called

    def test_gemini_sdk_exception_fallback(self, sample_graded_card):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API Network Timeout")

        listing = generate_marketplace_listing(
            sample_graded_card,
            mock=False,
            api_key="test_api_key_12345",
            client=mock_client
        )
        assert "ASKING PRICE" in listing
        assert "KEY SPECIFICATIONS" in listing


# ===========================================================================
# Tier 6: Unicode & Batch Generation
# ===========================================================================

class TestUnicodeAndBatch:
    """Validates international characters, zero prices, and batch calls."""

    def test_unicode_accents_and_japanese_characters(self):
        card = {
            "player": "Ronald Acu?a Jr. / ?? ??",
            "year": "2021",
            "set_name": "Topps Chrome",
            "variation": "Prism Refractor",
            "category": "Baseball",
            "condition": "PSA 10",
            "slab_serial_number": "12345678",
        }
        title = build_seo_title(card)
        assert "Acu?a" in title
        assert len(title) < 100

        listing = MockSalesGenerator.generate(card)
        assert "Acu?a" in listing

    def test_batch_listings_generation(self, sample_graded_card, sample_raw_card):
        cards = [sample_graded_card, sample_raw_card]
        prices = [1500.0, 320.0]
        results = generate_batch_marketplace_listings(cards, asking_prices=prices, mock=True)
        assert len(results) == 2
        assert "1,500.00" in results[0]
        assert "320.00" in results[1]


# ===========================================================================
# Tier 7: Database Staging Lookup Helper
# ===========================================================================

class TestDatabaseIntegration:
    """Validates generate_listing_for_card_id helper against SQLite."""

    def test_generate_for_card_id_success(self, sample_graded_card):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)
        card_id = insert_card(sample_graded_card, db_path=db_path)

        listing = generate_listing_for_card_id(db_path=db_path, card_id=card_id, mock=True)
        assert "Luka Doncic" in listing
        assert "48192041" in listing

        if os.path.exists(db_path):
            os.remove(db_path)

    def test_generate_for_invalid_card_id_raises_value_error(self):
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        init_db(db_path)

        with pytest.raises(ValueError, match="not found"):
            generate_listing_for_card_id(db_path=db_path, card_id=99999, mock=True)

        if os.path.exists(db_path):
            os.remove(db_path)
