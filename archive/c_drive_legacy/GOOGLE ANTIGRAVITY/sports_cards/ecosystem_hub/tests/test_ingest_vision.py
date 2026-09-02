"""
tests/test_ingest_vision.py - Comprehensive Test Suite for AI Vision Ingest Pipeline.
Tests deterministic MockVisionExtractor, google.genai SDK integration,
Pydantic schema validation, batch processing, circuit breaker, and SQLite persistence.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

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
)
from vision_ingest import (
    DEFAULT_VISION_MODEL,
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
def temp_image_file(tmp_path):
    """Creates a temporary dummy image file on disk."""
    img_file = tmp_path / "sample_test_card.jpg"
    img_file.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00")
    return str(img_file)


@pytest.fixture
def temp_db(tmp_path):
    """Provides a fresh isolated SQLite database for vision tests."""
    db_file = str(tmp_path / "test_vision_portfolio.db")
    init_db(db_file)
    return db_file


# ---------------------------------------------------------------------------
# Tier 1: Schema Validation & Normalization
# ---------------------------------------------------------------------------

class TestVisionExtractionSchema:
    """Tests Pydantic CardExtractionSchema behavior."""

    def test_schema_valid_raw_card(self):
        schema = CardExtractionSchema(
            player="Victor Wembanyama",
            year="2023",
            set_name="Panini Prizm",
            variation="",
            card_number="01",
            category=CardCategory.BASKETBALL,
            condition="Raw",
            slab_serial_number="",
            estimated_value=250.0,
            ai_status=AIStatus.CLEARED,
        )
        assert schema.player == "Victor Wembanyama"
        assert schema.card_number == "01"
        assert schema.condition == "Raw"
        assert schema.slab_serial_number == ""
        assert schema.ai_status == AIStatus.CLEARED

    def test_schema_valid_graded_card(self):
        schema = CardExtractionSchema(
            player="Luka Dončić",
            year="2020",
            set_name="Panini Prizm",
            variation="Silver Prizm",
            card_number="75",
            category=CardCategory.BASKETBALL,
            condition="PSA 10",
            slab_serial_number="48192041",
            estimated_value=350.0,
            ai_status=AIStatus.REVIEW_VARIATION,
        )
        assert schema.condition == "PSA 10"
        assert schema.slab_serial_number == "48192041"
        assert schema.ai_status == AIStatus.REVIEW_VARIATION

    def test_schema_card_number_preserves_leading_zeros(self):
        schema = CardExtractionSchema(
            player="Ronald Acuña Jr.",
            year="2019",
            set_name="Topps Chrome",
            card_number="007",
            category=CardCategory.BASEBALL,
        )
        assert schema.card_number == "007"
        assert isinstance(schema.card_number, str)


# ---------------------------------------------------------------------------
# Tier 2: MockVisionExtractor Determinism & Keyword Inference
# ---------------------------------------------------------------------------

class TestMockVisionExtractor:
    """Tests deterministic mock vision extractor."""

    def test_fixture_loading(self):
        fixtures = load_fixture_data()
        assert len(fixtures) >= 5
        for fix in fixtures:
            assert "player" in fix
            assert "year" in fix
            assert "set_name" in fix
            assert "category" in fix

    def test_known_fixture_keyword_matching(self):
        luka = MockVisionExtractor("path/to/sample_luka_front.jpg")
        assert "Luka" in luka.player
        assert luka.year == "2020"
        assert luka.category == CardCategory.BASKETBALL.value
        assert luka.condition == "PSA 10"
        assert luka.slab_serial_number == "48192041"

        zard = MockVisionExtractor("charizard_card.png")
        assert "Charizard" in zard.player
        assert zard.year == "1999"
        assert zard.category == CardCategory.POKEMON.value
        assert zard.condition == "SGC 10"

        ohtani = MockVisionExtractor("shohei_ohtani_refractor.jpg")
        assert "Ohtani" in ohtani.player
        assert ohtani.year == "2018"
        assert ohtani.category == CardCategory.BASEBALL.value
        assert ohtani.condition == "BGS 9.5"

    def test_filename_pattern_inference(self):
        custom = MockVisionExtractor("2021_panini_prizm_basketball_psa10_test.jpg")
        assert custom.year == "2021"
        assert custom.category == CardCategory.BASKETBALL.value
        assert custom.condition == "PSA 10"
        assert custom.slab_serial_number != ""

    def test_deterministic_hash_fallback(self):
        res1 = MockVisionExtractor("arbitrary_unknown_image_xyz.jpg")
        res2 = MockVisionExtractor("arbitrary_unknown_image_xyz.jpg")
        assert res1.player == res2.player
        assert res1.year == res2.year
        assert res1.set_name == res2.set_name
        assert res1.category == res2.category
        assert res1.condition == res2.condition

    def test_notes_formatting_in_mock(self):
        res = MockVisionExtractor("card.jpg", parent_image_id=8492, child_card_id=105)
        assert res.notes == "8492-105"

    def test_raw_condition_slab_isolation(self):
        res = MockVisionExtractor("sample_acuna_front.jpg")
        assert res.condition == "Raw"
        assert res.slab_serial_number == ""


# ---------------------------------------------------------------------------
# Tier 3: extract_card_from_image Offline & Fallback Modes
# ---------------------------------------------------------------------------

class TestExtractCardOffline:
    """Tests extract_card_from_image in offline and fallback modes."""

    def test_explicit_mock_flag(self, temp_image_file):
        card = extract_card_from_image(temp_image_file, mock=True)
        assert isinstance(card, CardExtractionSchema)
        assert card.category in VALID_CATEGORIES
        assert card.image == temp_image_file

    def test_missing_api_key_automatic_fallback(self, temp_image_file):
        with patch.dict(os.environ, {}, clear=True):
            card = extract_card_from_image(temp_image_file, mock=False)
            assert isinstance(card, CardExtractionSchema)
            assert card.category in VALID_CATEGORIES

    def test_dual_image_paths(self, tmp_path):
        front = str(tmp_path / "front.jpg")
        back = str(tmp_path / "back.jpg")
        Path(front).write_bytes(b"front")
        Path(back).write_bytes(b"back")

        card = extract_card_from_image(front, back_image_path=back, mock=True)
        assert card.image == front
        assert card.back_image == back


# ---------------------------------------------------------------------------
# Tier 4: Mocked Google GenAI SDK Interaction
# ---------------------------------------------------------------------------

class TestGeminiSDKExtraction:
    """Tests live SDK execution paths using mocked genai client."""

    def test_successful_gemini_client_extraction(self, temp_image_file):
        mock_response_json = """{
            "player": "Victor Wembanyama",
            "year": "2023",
            "set_name": "Panini Prizm",
            "variation": "Silver Prizm",
            "card_number": "136",
            "category": "Basketball",
            "condition": "PSA 10",
            "slab_serial_number": "88192031",
            "estimated_value": 850.0,
            "notes": "",
            "image": "",
            "back_image": "",
            "ai_status": "REVIEW VARIATION"
        }"""

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = mock_response_json
        mock_client.models.generate_content.return_value = mock_response

        card = extract_card_from_image(
            image_path=temp_image_file,
            mock=False,
            api_key="test_api_key_123",
            client=mock_client,
            parent_image_id=9001,
            child_card_id=1,
        )

        assert card.player == "Victor Wembanyama"
        assert card.year == "2023"
        assert card.variation == "Silver Prizm"
        assert card.category == CardCategory.BASKETBALL.value
        assert card.condition == "PSA 10"
        assert card.slab_serial_number == "88192031"
        assert card.notes == "9001-001"
        assert card.ai_status == AIStatus.REVIEW_VARIATION.value

        mock_client.models.generate_content.assert_called_once()
        call_kwargs = mock_client.models.generate_content.call_args.kwargs
        assert call_kwargs["model"] == DEFAULT_VISION_MODEL
        assert call_kwargs["config"].response_schema == CardExtractionSchema
        assert call_kwargs["config"].response_mime_type == "application/json"

    def test_missing_file_raises_error_in_live_mode(self):
        mock_client = MagicMock()
        with pytest.raises(FileNotFoundError):
            extract_card_from_image(
                image_path="non_existent_card_path_12345.jpg",
                mock=False,
                api_key="test_key",
                client=mock_client,
            )


# ---------------------------------------------------------------------------
# Tier 5: Record Conversion & Database Ingestion Bridge
# ---------------------------------------------------------------------------

class TestVisionDatabaseIntegration:
    """Tests converting extracted card schemas to CardRecord and persisting to SQLite."""

    def test_extraction_to_card_record_conversion(self):
        extraction = CardExtractionSchema(
            player="Luka Dončić",
            year="2020",
            set_name="Panini Prizm",
            variation="Silver Prizm",
            card_number="75",
            category=CardCategory.BASKETBALL,
            condition="PSA 10",
            slab_serial_number="48192041",
            estimated_value=350.0,
            image="sample_luka.jpg",
        )

        record = extraction_to_card_record(
            extraction,
            investment=150.0,
            quantity=1,
            parent_image_id=8492,
            child_card_id=101,
            tags="graded, prizm",
        )

        assert isinstance(record, CardRecord)
        assert record.investment == 150.0
        assert record.notes == "8492-101"
        assert record.tags == "graded, prizm"
        assert record.query == "2020 Panini Prizm Luka Dončić Silver Prizm PSA 10"
        assert record.ai_status == AIStatus.REVIEW_VARIATION.value

    def test_persist_extracted_card_to_db(self, temp_db):
        extraction = MockVisionExtractor("sample_luka_front.jpg", parent_image_id=8492, child_card_id=101)
        record = extraction_to_card_record(extraction, investment=120.0)

        card_id = insert_card(record, db_path=temp_db)
        assert card_id is not None
        assert card_id > 0

        saved = get_card_by_id(card_id, db_path=temp_db)
        assert saved is not None
        assert saved["player"] == "Luka Dončić"
        assert saved["investment"] == 120.0
        assert saved["notes"] == "8492-101"

    def test_ingest_vision_card_helper(self, temp_db):
        extraction = MockVisionExtractor("charizard_card.png")
        card_id = ingest_vision_card(
            extraction=extraction,
            parent_image_id=9900,
            child_card_id=105,
            investment=500.0,
            db_path=temp_db,
        )
        assert card_id > 0
        saved = get_card_by_id(card_id, db_path=temp_db)
        assert saved["player"] == "Charizard"
        assert saved["notes"] == "9900-105"
        assert saved["investment"] == 500.0

    def test_ingest_vision_batch_helper(self, temp_db):
        extractions = [
            MockVisionExtractor("sample_luka_front.jpg"),
            MockVisionExtractor("sample_acuna_front.jpg"),
            MockVisionExtractor("charizard_card.png"),
        ]
        ids = ingest_vision_batch(
            extractions_or_paths=extractions,
            parent_id=8800,
            investment=25.0,
            db_path=temp_db,
        )
        assert len(ids) == 3
        cards = get_all_cards(db_path=temp_db)
        assert len(cards) == 3
        notes = [c["notes"] for c in cards]
        assert "8800-101" in notes
        assert "8800-102" in notes
        assert "8800-103" in notes


# ---------------------------------------------------------------------------
# Tier 6: Batch Processing & Circuit Breaker
# ---------------------------------------------------------------------------

class TestBatchVisionProcessing:
    """Tests batch ingestion pipelines and circuit breaker."""

    def test_batch_extract_cards(self):
        paths = ["card1.jpg", "card2.jpg", "card3.jpg"]
        results = batch_extract_cards(paths, mock=True, parent_image_id=100)
        assert len(results) == 3
        assert results[0].notes == "0100-001"
        assert results[1].notes == "0100-002"
        assert results[2].notes == "0100-003"

    def test_batch_extract_to_records(self):
        paths = ["sample_luka_front.jpg", "sample_charizard.png"]
        records = batch_extract_to_records(paths, mock=True, investment=50.0, parent_image_id=200)
        assert len(records) == 2
        for r in records:
            assert isinstance(r, CardRecord)
            assert r.investment == 50.0

    def test_batch_circuit_breaker_limit(self):
        paths = [f"card_{i}.jpg" for i in range(501)]
        with pytest.raises(ValueError, match="circuit breaker"):
            batch_extract_cards(paths, mock=True)


# ---------------------------------------------------------------------------
# Tier 7: Edge Cases & Unicode Handling
# ---------------------------------------------------------------------------

class TestVisionEdgeCases:
    """Tests non-standard inputs, Unicode names, and constraint isolations."""

    def test_vision_unicode_players(self):
        extraction = CardExtractionSchema(
            player="Shohei Ohtani (大谷 翔平)",
            year="2018",
            set_name="Bowman Chrome",
            variation="Refractor",
            card_number="BCP-1",
            category=CardCategory.BASEBALL,
            condition="BGS 9.5",
            slab_serial_number="0014892102",
        )
        record = extraction_to_card_record(extraction)
        assert "大谷 翔平" in record.player
        assert "大谷 翔平" in record.query

    def test_vision_multi_year_normalization(self):
        extraction = CardExtractionSchema(
            player="Giannis Antetokounmpo",
            year="2019-20",
            set_name="Panini Prizm",
            card_number="100",
            category=CardCategory.BASKETBALL,
        )
        record = extraction_to_card_record(extraction)
        assert record.year == "2019"

    def test_vision_raw_slab_serial_isolation(self):
        extraction = CardExtractionSchema(
            player="Stephen Curry",
            year="2009",
            set_name="Topps",
            card_number="305",
            category=CardCategory.BASKETBALL,
            condition="Raw",
            slab_serial_number="",
        )
        record = extraction_to_card_record(extraction)
        assert record.condition == "Raw"
        assert record.slab_serial_number == ""
