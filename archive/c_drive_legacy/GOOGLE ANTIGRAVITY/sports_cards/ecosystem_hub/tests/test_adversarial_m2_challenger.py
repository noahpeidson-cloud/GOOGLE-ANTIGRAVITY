"""
tests/test_adversarial_m2_challenger.py - Adversarial Stress & Fuzzing Harness for AI Vision Ingest.
Authored by Teamwork Preview Challenger (Agent Challenger M2).

Target: sports_cards/ecosystem_hub/vision_ingest.py, models.py, database.py.
Test Dimensions:
1. 60+ Diverse & Corrupted Image Filenames (Unicode, SQLi, XSS, Cmd Injection, Long Paths, Null Bytes, Emojis, URLs).
2. Input Fuzzing: Missing Parameters, Whitespace, Invalid Categories, Hyphenated Conditions, Slab Serial on Raw.
3. 500-Card Batch Circuit Breaker Enforcement (501 items raises ValueError / ValidationError).
4. Auto-flagging of Variations as 'REVIEW VARIATION' across all pipeline layers.
5. End-to-End Database Ingestion Integrity & Relational Parent-Child Key Verification.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

# Ensure ecosystem_hub is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    AIStatus,
    CardCategory,
    CardExtractionSchema,
    CardRecord,
    CardBatchCreate,
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
)
from vision_ingest import (
    MockVisionExtractor,
    batch_extract_cards,
    batch_extract_to_records,
    extract_card_from_image,
    extraction_to_card_record,
    ingest_vision_batch,
    ingest_vision_card,
    load_fixture_data,
)


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated SQLite database."""
    db_file = str(tmp_path / "test_adversarial_vision.db")
    init_db(db_file)
    return db_file


# ===========================================================================
# 1. 60+ Diverse, Corrupted, Adversarial Filenames
# ===========================================================================

ADVERSARIAL_FILENAMES = [
    # Plain standard
    "card.jpg",
    "image_front.png",
    "front.jpeg",
    "scan_001.webp",
    "photo.tiff",
    # Known players & diacritics
    "Luka Dončić.jpg",
    "luka-doncic-2020-prizm.png",
    "Shohei Ohtani (大谷 翔平).png",
    "shohei_ohtani_refractor.jpg",
    "Ronald Acuña Jr.jpg",
    "ronald_acuna_jr_topps.jpeg",
    "Connor McDavid_2015.jpg",
    "Patrick Mahomes II.png",
    "Lionel Messi 2004.jpg",
    "Blue-Eyes White Dragon 1st.jpg",
    "Charizard Base Set.png",
    "Black Lotus Alpha.jpeg",
    "Jon Jones UFC Prizm.jpg",
    "Max Verstappen F1 TAG 10.jpg",
    "Tiger Woods 2001 Upper Deck.png",
    # Structured filenames with year, sport, grader
    "2021_panini_prizm_basketball_psa10_test.jpg",
    "2020_topps_chrome_baseball_bgs9.5_silver.png",
    "1999_pokemon_charizard_sgc10.jpg",
    "2002_yugioh_blue_eyes_cgc9.5_holo.png",
    "2021_panini_select_football_tag10_silver.jpeg",
    "1986_fleer_basketball_bvg9_jordan.jpg",
    # Malformed & extreme length
    "a" * 300 + ".jpg",
    "x" * 500 + ".png",
    ".jpg",
    ".png",
    ".",
    "   .jpg",
    "   ",
    # Special characters & symbols
    "!@#$%^&*()_+=~[]{}|;:,.<>?_card.jpg",
    "card+with+plus+signs.png",
    "card(1)[final]{v2}#draft.jpg",
    "card__double__underscore__2020.jpg",
    "card--double--hyphen--2021.png",
    # Mixed path separators & directory traversals
    "foo/bar/baz/card.jpg",
    "foo\\bar\\baz\\card.png",
    "mixed/slashes\\path//card.jpeg",
    "../../../../etc/passwd_card.jpg",
    "..\\..\\windows\\system32_card.png",
    # Unicode emojis & mathematical symbols
    "🔥_card_💎_100%_🚀.jpg",
    "🏆_superstar_goat_🐐.png",
    "π_card_∑_∫_∂.png",
    "карточка_спорт_2020.jpg",
    "トレーディングカード_2021.png",
    "بطاقة_كرة_القدم.jpg",
    # SQL injection attack patterns
    "'; DROP TABLE cards; --.jpg",
    "card' OR '1'='1.png",
    "1 UNION SELECT * FROM cards.jpg",
    # XSS and HTML injection patterns
    "<script>alert(1)</script>.jpg",
    "<img src=x onerror=alert(1)>.png",
    "<b>bold_player</b>.jpg",
    # Command injection attack patterns
    "card_$(rm -rf /).png",
    "card_`whoami`.jpg",
    "card & dir & echo test.jpg",
    "card | ping 127.0.0.1.png",
    # Escape sequences & control characters
    "card\\nnewline.jpg",
    "card\\ttab.png",
    "card\\rreturn.jpg",
    # Format string specifiers
    "%s%s%s%s%s%n%x%d.jpg",
    "{player}_{year}_{set}.jpg",
    # URLs and Query parameters
    "https://example.com/cards/2020_prizm_luka_psa10.jpg?v=1&token=xyz#anchor",
    "http://127.0.0.1:8000/media/uploads/card_001.png",
    # Base64 and Hexadecimal encoded strings
    "Y2FyZF9pbWFnZV9kYXRhXzIwMjA=.jpg",
    "0x48656c6c6f20576f726c64.png",
    # Numeric-only
    "1234567890.jpg",
    "0000000000.png",
    "99999999999999999999.jpg",
    # Mixed casing
    "2020_PANINI_PRIZM_BASKETBALL_PSA10.JPG",
    "CHARIZARD_1999_POKEMON_SGC10.PNG",
]


class TestAdversarialFilenames:
    """Stress tests offline vision extraction across 60+ diverse and adversarial filenames."""

    def test_fixture_bank_contains_valid_entries(self):
        fixtures = load_fixture_data()
        assert len(fixtures) >= 5
        for fix in fixtures:
            assert isinstance(fix.get("player"), str)
            assert isinstance(fix.get("year"), (str, int))
            assert isinstance(fix.get("category"), str)

    @pytest.mark.parametrize("filename", ADVERSARIAL_FILENAMES)
    def test_offline_extraction_all_adversarial_filenames(self, filename: str):
        """Every adversarial filename must successfully extract a valid CardExtractionSchema without unhandled exceptions."""
        result = MockVisionExtractor(filename)
        assert isinstance(result, CardExtractionSchema)
        assert result.player and len(result.player.strip()) > 0
        assert result.year and len(result.year.strip()) >= 4
        assert result.set_name and len(result.set_name.strip()) > 0
        assert result.category in VALID_CATEGORIES
        assert result.condition and len(result.condition.strip()) > 0
        assert isinstance(result.estimated_value, (int, float))
        assert result.estimated_value >= 0.0
        assert result.ai_status in (AIStatus.CLEARED, AIStatus.REVIEW_VARIATION, AIStatus.NEEDS_REVIEW)

        # Confirm that if Condition is Raw, slab serial number is strictly empty
        if result.condition == "Raw":
            assert result.slab_serial_number == ""

        # Confirm conversion to CardRecord works cleanly
        record = extraction_to_card_record(result)
        assert isinstance(record, CardRecord)
        assert record.category in VALID_CATEGORIES
        assert len(record.query) > 0

    def test_raw_bytes_input_to_extract_card(self):
        """Passing raw byte payloads to extract_card_from_image with mock=True must succeed."""
        raw_data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00"
        result = extract_card_from_image(raw_data, mock=True)
        assert isinstance(result, CardExtractionSchema)
        assert result.category in VALID_CATEGORIES

    def test_accent_insensitive_matching(self):
        """Names with accents (Luka Dončić, Ronald Acuña Jr.) match fixtures whether accented or unaccented."""
        res_accent = MockVisionExtractor("luka_dončić_prizm.jpg")
        res_plain = MockVisionExtractor("luka_doncic_prizm.jpg")
        assert "Luka" in res_accent.player
        assert "Luka" in res_plain.player
        assert res_accent.player == res_plain.player

        res_acuna_acc = MockVisionExtractor("ronald_acuña_jr.jpg")
        res_acuna_plain = MockVisionExtractor("ronald_acuna_jr.jpg")
        assert "Acuña" in res_acuna_acc.player or "Acuna" in res_acuna_acc.player
        assert res_acuna_acc.player == res_acuna_plain.player


# ===========================================================================
# 2. Input Fuzzing: Missing Parameters, Empty Strings, Invalid Types
# ===========================================================================

class TestInputFuzzingAndValidation:
    """Stress tests boundary validation, illegal formats, and error handling."""

    def test_missing_required_fields_in_card_record(self):
        """CardRecord must reject missing or whitespace-only required fields."""
        # Missing player
        with pytest.raises(ValidationError):
            CardRecord(
                player="",
                year="2020",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
            )

        with pytest.raises(ValidationError):
            CardRecord(
                player="   ",
                year="2020",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
            )

        # Missing set_name
        with pytest.raises(ValidationError):
            CardRecord(
                player="Luka Dončić",
                year="2020",
                set_name="",
                category=CardCategory.BASKETBALL,
            )

        # Missing year
        with pytest.raises(ValidationError):
            CardRecord(
                player="Luka Dončić",
                year="",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
            )

    @pytest.mark.parametrize("bad_year", ["abc", "20", "99", "invalid", "-2020", "2020111"])
    def test_invalid_year_formats(self, bad_year: str):
        """Invalid year formats must be rejected by CardRecord."""
        with pytest.raises(ValidationError):
            CardRecord(
                player="Luka Dončić",
                year=bad_year,
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
            )

    @pytest.mark.parametrize(
        "season_input,expected_year",
        [
            ("2020-21", "2020"),
            ("2019/20", "2019"),
            ("2021-2022", "2021"),
            ("1996-97", "1996"),
        ],
    )
    def test_multi_year_season_normalization(self, season_input: str, expected_year: str):
        """Multi-year season notations must normalize to the 4-digit opening year."""
        rec = CardRecord(
            player="Kobe Bryant",
            year=season_input,
            set_name="Topps Chrome",
            category=CardCategory.BASKETBALL,
        )
        assert rec.year == expected_year

    @pytest.mark.parametrize("bad_cat", ["Cricket", "Rugby", "SoccerBall", "Auto", "123", "", None])
    def test_invalid_categories_rejected(self, bad_cat: Any):
        """Non-permitted categories must raise a ValidationError."""
        with pytest.raises(ValidationError):
            CardRecord(
                player="Test Player",
                year="2020",
                set_name="Test Set",
                category=bad_cat,
            )

    @pytest.mark.parametrize(
        "alias_input,expected_canonical",
        [
            ("ufc", "UFC/MMA"),
            ("MMA", "UFC/MMA"),
            ("pop culture", "PopCulture"),
            ("popculture", "PopCulture"),
            ("dragon ball z", "Dragonballz"),
            ("flesh & blood", "Flesh and Blood"),
            ("flesh and blood", "Flesh and Blood"),
            ("BASKETBALL", "Basketball"),
            ("baseball", "Baseball"),
        ],
    )
    def test_category_aliasing_and_normalization(self, alias_input: str, expected_canonical: str):
        """Category aliases and lowercased names must resolve to canonical CardCategory values."""
        rec = CardRecord(
            player="Jon Jones",
            year="2021",
            set_name="Panini Prizm",
            category=alias_input,
        )
        assert rec.category == expected_canonical

    @pytest.mark.parametrize("hyphen_cond", ["PSA-10", "BGS-9.5", "SGC-10", "CGC-9.5", "TAG-10", "BVG-8.5"])
    def test_hyphenated_graded_condition_rejected(self, hyphen_cond: str):
        """Graded conditions with hyphens (e.g. PSA-10) are strictly forbidden."""
        with pytest.raises(ValidationError, match="hyphens"):
            CardRecord(
                player="Luka Dončić",
                year="2020",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition=hyphen_cond,
            )

    def test_raw_condition_with_slab_serial_rejected(self):
        """A card in Raw condition cannot have a slab serial number."""
        with pytest.raises(ValidationError, match="Slab serial number must be blank"):
            CardRecord(
                player="Luka Dončić",
                year="2020",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition="Raw",
                slab_serial_number="48192041",
            )

    def test_negative_exclusions_in_raw_query_rejected(self):
        """Raw cards with negative grader exclusions (-BGS, -PSA, etc.) in query must be rejected."""
        with pytest.raises(ValidationError, match="Negative exclusions are forbidden"):
            CardRecord(
                player="Luka Dončić",
                year="2020",
                set_name="Panini Prizm",
                category=CardCategory.BASKETBALL,
                condition="Raw",
                query="2020 Panini Prizm Luka Dončić -PSA -BGS",
            )

    def test_negative_values_and_zero_quantity_handling(self):
        """Test how extraction_to_card_record handles negative investments and zero quantities."""
        schema = CardExtractionSchema(
            player="Stephen Curry",
            year="2009",
            set_name="Topps",
            category=CardCategory.BASKETBALL,
        )
        # Clamps negative investment to 0.0 and zero/negative quantity to 1
        rec = extraction_to_card_record(schema, investment=-100.0, quantity=0)
        assert rec.investment == 0.0
        assert rec.quantity == 1

        rec2 = extraction_to_card_record(schema, investment=-5.5, quantity=-10)
        assert rec2.investment == 0.0
        assert rec2.quantity == 1


# ===========================================================================
# 3. 500-Card Batch Circuit Breaker
# ===========================================================================

class TestCircuitBreakerEnforcement:
    """Stress tests the 500-card batch circuit breaker across schema and pipeline functions."""

    def test_batch_extract_cards_500_limit_allowed(self):
        """A batch of exactly 500 image paths is accepted."""
        paths = [f"card_{i:04d}.jpg" for i in range(CIRCUIT_BREAKER_BATCH_LIMIT)]
        results = batch_extract_cards(paths, mock=True)
        assert len(results) == 500

    def test_batch_extract_cards_501_raises_value_error(self):
        """A batch of 501 image paths MUST raise ValueError."""
        paths = [f"card_{i:04d}.jpg" for i in range(501)]
        with pytest.raises(ValueError, match="circuit breaker"):
            batch_extract_cards(paths, mock=True)

    def test_batch_extract_cards_1000_raises_value_error(self):
        """A massive batch of 1000 image paths MUST raise ValueError."""
        paths = [f"card_{i:04d}.jpg" for i in range(1000)]
        with pytest.raises(ValueError, match="circuit breaker"):
            batch_extract_cards(paths, mock=True)

    def test_card_batch_create_pydantic_500_allowed(self):
        """CardBatchCreate allows up to 500 CardRecord objects."""
        base_record = CardRecord(
            player="Test Player",
            year="2020",
            set_name="Test Set",
            category=CardCategory.BASKETBALL,
        )
        batch = CardBatchCreate(cards=[base_record] * 500)
        assert len(batch.cards) == 500

    def test_card_batch_create_pydantic_501_raises_validation_error(self):
        """CardBatchCreate rejects 501 CardRecord objects via Pydantic validator."""
        base_record = CardRecord(
            player="Test Player",
            year="2020",
            set_name="Test Set",
            category=CardCategory.BASKETBALL,
        )
        with pytest.raises(ValidationError):
            CardBatchCreate(cards=[base_record] * 501)

    def test_card_batch_create_empty_raises_validation_error(self):
        """CardBatchCreate rejects an empty list of cards."""
        with pytest.raises(ValidationError):
            CardBatchCreate(cards=[])


# ===========================================================================
# 4. Variation Auto-Flagging ('REVIEW VARIATION')
# ===========================================================================

class TestVariationAutoFlagging:
    """Verifies that cards containing variations are auto-flagged for human review."""

    @pytest.mark.parametrize(
        "var_name",
        [
            "Silver Prizm",
            "Refractor",
            "Gold Prizm /10",
            "1st Edition Holo",
            "Orange Refractor /25",
            "The Rookies",
            "Pink Camo",
            "Cracked Ice /25",
        ],
    )
    def test_variation_auto_flags_review_variation_in_schema(self, var_name: str):
        """CardExtractionSchema and extraction_to_card_record must promote variation cards to REVIEW VARIATION."""
        schema = CardExtractionSchema(
            player="Luka Dončić",
            year="2020",
            set_name="Panini Prizm",
            variation=var_name,
            card_number="75",
            category=CardCategory.BASKETBALL,
            condition="PSA 10",
            slab_serial_number="48192041",
            ai_status=AIStatus.CLEARED,  # Default incoming from extraction
        )
        record = extraction_to_card_record(schema)
        assert record.ai_status == AIStatus.REVIEW_VARIATION.value

    def test_base_card_without_variation_remains_cleared(self):
        """Base cards with empty variation must remain CLEARED."""
        schema = CardExtractionSchema(
            player="Ronald Acuña Jr.",
            year="2019",
            set_name="Topps Chrome",
            variation="",
            card_number="001",
            category=CardCategory.BASEBALL,
            condition="Raw",
            ai_status=AIStatus.CLEARED,
        )
        record = extraction_to_card_record(schema)
        assert record.ai_status == AIStatus.CLEARED.value

    def test_explicit_needs_review_is_preserved(self):
        """Cards already flagged as NEEDS REVIEW must not be downgraded or changed."""
        schema = CardExtractionSchema(
            player="Patrick Mahomes",
            year="2017",
            set_name="Panini Donruss",
            variation="The Rookies",
            card_number="TR-10",
            category=CardCategory.FOOTBALL,
            condition="Raw",
            ai_status=AIStatus.NEEDS_REVIEW,
        )
        record = extraction_to_card_record(schema)
        assert record.ai_status == AIStatus.NEEDS_REVIEW.value

    def test_card_record_direct_validation_auto_promotes_variation(self):
        """Direct instantiation of CardRecord with variation and CLEARED promotes to REVIEW VARIATION."""
        record = CardRecord(
            player="Shohei Ohtani",
            year="2018",
            set_name="Bowman Chrome",
            variation="Refractor",
            category=CardCategory.BASEBALL,
            condition="BGS 9.5",
            slab_serial_number="0014892102",
            ai_status=AIStatus.CLEARED,
        )
        assert record.ai_status == AIStatus.REVIEW_VARIATION.value


# ===========================================================================
# 5. Database Ingestion Integrity & Relational Notes
# ===========================================================================

class TestDatabaseIngestionIntegrity:
    """Stress tests relational tracking notes, batch insertion safety, and queries."""

    def test_format_notes_valid(self):
        assert format_notes(8492, 105) == "8492-105"
        assert format_notes("8492", "105") == "8492-105"
        assert format_notes(42, 1) == "0042-001"
        assert format_notes("0042-001", "") == "0042-001"

    @pytest.mark.parametrize("bad_p,bad_c", [("abc", "105"), (8492, "xyz"), (-1, 5), (10, -5)])
    def test_format_notes_invalid_raises_error(self, bad_p: Any, bad_c: Any):
        with pytest.raises(ValueError):
            format_notes(bad_p, bad_c)

    def test_batch_ingest_preserves_sequential_notes(self, temp_db):
        """Batch ingestion under a parent ID assigns correct sequential child IDs."""
        paths = [
            "sample_luka_front.jpg",
            "sample_acuna_front.jpg",
            "charizard_card.png",
            "shohei_ohtani_refractor.jpg",
        ]
        ids = ingest_vision_batch(paths, parent_id=7700, db_path=temp_db)
        assert len(ids) == 4

        cards = get_all_cards(db_path=temp_db, order_by="id ASC")
        assert len(cards) == 4
        notes = [c["notes"] for c in cards]
        assert notes == ["7700-101", "7700-102", "7700-103", "7700-104"]

    def test_subsequent_batch_ingest_increments_child_ids(self, temp_db):
        """A subsequent batch under the same parent ID correctly increments from the last child ID."""
        batch1 = ["sample_luka_front.jpg", "sample_acuna_front.jpg"]
        ids1 = ingest_vision_batch(batch1, parent_id=5500, db_path=temp_db)
        assert len(ids1) == 2

        batch2 = ["charizard_card.png", "shohei_ohtani_refractor.jpg"]
        ids2 = ingest_vision_batch(batch2, parent_id=5500, db_path=temp_db)
        assert len(ids2) == 2

        cards = get_all_cards(db_path=temp_db, order_by="id ASC")
        assert len(cards) == 4
        notes = [c["notes"] for c in cards]
        assert notes == ["5500-101", "5500-102", "5500-103", "5500-104"]

    def test_large_batch_ingest_chunking_integrity(self, temp_db):
        """Batch inserting 100 items persists all records with complete data integrity."""
        extractions = [
            MockVisionExtractor(f"2021_panini_prizm_basketball_psa10_test_{i}.jpg")
            for i in range(100)
        ]
        ids = ingest_vision_batch(extractions, parent_id=9000, investment=10.0, db_path=temp_db)
        assert len(ids) == 100

        cards = get_all_cards(db_path=temp_db)
        assert len(cards) == 100
        for card in cards:
            assert card["investment"] == 10.0
            assert card["category"] == "Basketball"
            assert card["condition"] == "PSA 10"


# ===========================================================================
# 6. Mock Gemini SDK Failure Modes & Network Resilience
# ===========================================================================

class TestGeminiSDKFailureModes:
    """Stress tests live SDK call error propagation and handling."""

    def test_gemini_api_empty_response_raises_value_error(self, tmp_path):
        dummy_img = str(tmp_path / "card.jpg")
        Path(dummy_img).write_bytes(b"dummy")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = ""  # Empty response text
        mock_client.models.generate_content.return_value = mock_response

        with pytest.raises(ValueError, match="empty response"):
            extract_card_from_image(
                image_path=dummy_img,
                mock=False,
                api_key="fake_key",
                client=mock_client,
            )

    def test_gemini_api_malformed_json_raises_validation_error(self, tmp_path):
        dummy_img = str(tmp_path / "card.jpg")
        Path(dummy_img).write_bytes(b"dummy")

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = '{"player": "Test", "year": "invalid_json...'
        mock_client.models.generate_content.return_value = mock_response

        with pytest.raises(ValidationError):
            extract_card_from_image(
                image_path=dummy_img,
                mock=False,
                api_key="fake_key",
                client=mock_client,
            )

    def test_gemini_api_upstream_exception_propagates(self, tmp_path):
        dummy_img = str(tmp_path / "card.jpg")
        Path(dummy_img).write_bytes(b"dummy")

        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("Quota exceeded / Rate limited 429")

        with pytest.raises(RuntimeError, match="Quota exceeded"):
            extract_card_from_image(
                image_path=dummy_img,
                mock=False,
                api_key="fake_key",
                client=mock_client,
            )
