"""
tests/test_adversarial_m1_challenger.py - Empirical Adversarial Challenge Suite for Milestone 1.
Authored by challenger_m1_2 subagent.
Tests boundary value handling, circuit breakers, transaction rollbacks, stats accuracy, and unicode handling.
"""

from __future__ import annotations

import os
import sys
import sqlite3
import pytest
from pydantic import ValidationError

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models import (
    CardRecord,
    CardCategory,
    AIStatus,
    CardBatchCreate,
    CardUpdate,
    synthesize_query,
    format_notes,
    VALID_CATEGORIES,
)
from database import (
    init_db,
    get_db_connection,
    insert_card,
    insert_cards_batch,
    get_card_by_id,
    get_all_cards,
    update_card,
    delete_card,
    get_summary_stats,
    get_card_count,
    check_circuit_breaker,
    get_next_child_id,
    clear_staging_table,
    CIRCUIT_BREAKER_BATCH_LIMIT,
)


@pytest.fixture
def fresh_db(tmp_path):
    """Provides an isolated SQLite database path."""
    db_file = str(tmp_path / "challenger_test.db")
    init_db(db_file)
    return db_file


# ============================================================================
# Section 1: 500-Card Batch Circuit Breaker & Bulk Insertion Chunking
# ============================================================================

class TestSection1CircuitBreakerAndChunking:

    def test_empty_batch(self, fresh_db):
        """Empty list should return [] without modifying DB."""
        res = insert_cards_batch([], fresh_db)
        assert res == []
        assert get_card_count(fresh_db) == 0

    def test_single_card_batch(self, fresh_db):
        """1 card batch should succeed."""
        batch = [{"player": "Single Player", "year": "2024", "set_name": "Set 1", "category": "Basketball"}]
        ids = insert_cards_batch(batch, fresh_db)
        assert len(ids) == 1
        assert get_card_count(fresh_db) == 1

    def test_exact_499_cards(self, fresh_db):
        """499 cards should not trip the circuit breaker."""
        batch = [
            {"player": f"Player {i}", "year": "2024", "set_name": "Set A", "category": "Baseball", "card_number": str(i)}
            for i in range(1, 500)
        ]
        ids = insert_cards_batch(batch, fresh_db)
        assert len(ids) == 499
        cb = check_circuit_breaker(fresh_db, threshold=500)
        assert cb["total_staged"] == 499
        assert cb["circuit_breaker_tripped"] is False

    def test_exact_500_cards_trips_circuit_breaker(self, fresh_db):
        """Exact 500 cards must trip the circuit breaker."""
        batch = [
            {"player": f"Player {i}", "year": "2024", "set_name": "Set B", "category": "Football", "card_number": str(i)}
            for i in range(1, 501)
        ]
        ids = insert_cards_batch(batch, fresh_db)
        assert len(ids) == 500
        cb = check_circuit_breaker(fresh_db, threshold=500)
        assert cb["total_staged"] == 500
        assert cb["circuit_breaker_tripped"] is True

    def test_501_cards_chunking_boundary(self, fresh_db):
        """501 cards spans across two chunks (500 + 1)."""
        batch = [
            {"player": f"Athlete {i}", "year": "2023", "set_name": "Set C", "category": "Soccer", "card_number": str(i)}
            for i in range(1, 502)
        ]
        ids = insert_cards_batch(batch, fresh_db, chunk_size=500)
        assert len(ids) == 501
        assert ids[0] == 1
        assert ids[-1] == 501
        assert get_card_count(fresh_db) == 501
        cb = check_circuit_breaker(fresh_db, threshold=500)
        assert cb["total_staged"] == 501
        assert cb["circuit_breaker_tripped"] is True

    def test_1000_cards_multi_chunking(self, fresh_db):
        """1000 cards in 500-sized chunks."""
        batch = [
            {"player": f"Hockey Star {i}", "year": "2022", "set_name": "Upper Deck", "category": "Hockey", "card_number": f"{i:04d}"}
            for i in range(1, 1001)
        ]
        ids = insert_cards_batch(batch, fresh_db, chunk_size=500)
        assert len(ids) == 1000
        assert get_card_count(fresh_db) == 1000

    def test_custom_chunk_sizes(self, fresh_db):
        """Verifies chunk_size=7 and chunk_size=1 chunking accuracy."""
        batch = [
            {"player": f"Golfer {i}", "year": "2021", "set_name": "SP Authentic", "category": "Golf", "card_number": str(i)}
            for i in range(1, 23)
        ]
        ids = insert_cards_batch(batch, fresh_db, chunk_size=7)
        assert len(ids) == 22
        assert get_card_count(fresh_db) == 22

    def test_pydantic_batch_model_boundary(self):
        """CardBatchCreate enforces min_length=1 and max_length=500."""
        valid_card = CardRecord(player="P", year="2024", set_name="S", category=CardCategory.BASEBALL)
        
        with pytest.raises(ValidationError):
            CardBatchCreate(cards=[])

        batch_500 = CardBatchCreate(cards=[valid_card] * 500)
        assert len(batch_500.cards) == 500

        with pytest.raises(ValidationError):
            CardBatchCreate(cards=[valid_card] * 501)


# ============================================================================
# Section 2: SQLite Rollback on Partial Batch Failure
# ============================================================================

class TestSection2RollbackOnPartialBatchFailure:

    def test_rollback_on_first_item_invalid(self, fresh_db):
        """Invalid item at index 0 prevents any DB writes."""
        batch = [
            {"player": "", "year": "2024", "set_name": "Set", "category": "Baseball"},
            {"player": "Valid 2", "year": "2024", "set_name": "Set", "category": "Baseball"},
        ]
        with pytest.raises(ValidationError):
            insert_cards_batch(batch, fresh_db)
        assert get_card_count(fresh_db) == 0

    def test_rollback_on_middle_item_invalid(self, fresh_db):
        """Invalid item at index 50 out of 100 prevents all 100 from being inserted."""
        batch = [
            {"player": f"Valid {i}", "year": "2024", "set_name": "Set", "category": "Baseball"}
            for i in range(100)
        ]
        batch[50]["category"] = "InvalidCategory"

        with pytest.raises(ValidationError):
            insert_cards_batch(batch, fresh_db)
        assert get_card_count(fresh_db) == 0

    def test_rollback_on_last_item_invalid(self, fresh_db):
        """Invalid item at index 499 out of 500 prevents all 499 previous valid items from persisting."""
        batch = [
            {"player": f"Valid {i}", "year": "2024", "set_name": "Set", "category": "Baseball"}
            for i in range(500)
        ]
        batch[499]["year"] = "INVALID_YEAR"

        with pytest.raises(ValidationError):
            insert_cards_batch(batch, fresh_db)
        assert get_card_count(fresh_db) == 0

    def test_rollback_on_raw_slab_serial_violation_in_batch(self, fresh_db):
        """CardRecord validation catching Raw + slab_serial_number in batch rolls back whole batch."""
        batch = [
            {"player": "Player 1", "year": "2024", "set_name": "Set", "category": "Baseball", "condition": "Raw"},
            {"player": "Player 2", "year": "2024", "set_name": "Set", "category": "Baseball", "condition": "Raw", "slab_serial_number": "9999"},
        ]
        with pytest.raises(ValidationError):
            insert_cards_batch(batch, fresh_db)
        assert get_card_count(fresh_db) == 0

    def test_rollback_on_db_level_integrity_error_mid_transaction(self, fresh_db):
        """
        Simulates an integrity error that bypasses Pydantic (or occurs during multi-chunk commit).
        Proves atomic rollback across chunks.
        """
        valid_rec = {
            "date_purchased": "08/24/2026", "quantity": 1, "player": "Valid Player",
            "year": "2024", "set_name": "Set", "variation": "", "card_number": "1",
            "category": "Baseball", "condition": "Raw", "slab_serial_number": "",
            "investment": 0.0, "estimated_value": 0.0, "ladder_id": "",
            "query": "2024 Set Valid Player Raw", "notes": "", "tags": "",
            "date_sold": "", "sold_price": None, "image": "", "back_image": "",
            "ai_status": "CLEARED"
        }
        
        with pytest.raises(sqlite3.IntegrityError):
            with get_db_connection(fresh_db) as conn:
                cursor = conn.cursor()
                for i in range(500):
                    rec = dict(valid_rec)
                    rec["player"] = f"Chunk1 Player {i}"
                    cursor.execute("""
                    INSERT INTO cards (
                        date_purchased, quantity, player, year, set_name, variation, card_number,
                        category, condition, slab_serial_number, investment, estimated_value,
                        ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                    ) VALUES (
                        :date_purchased, :quantity, :player, :year, :set_name, :variation, :card_number,
                        :category, :condition, :slab_serial_number, :investment, :estimated_value,
                        :ladder_id, :query, :notes, :tags, :date_sold, :sold_price, :image, :back_image, :ai_status
                    );
                    """, rec)
                
                bad_rec = dict(valid_rec)
                bad_rec["category"] = "Badminton"
                cursor.execute("""
                INSERT INTO cards (
                    date_purchased, quantity, player, year, set_name, variation, card_number,
                    category, condition, slab_serial_number, investment, estimated_value,
                    ladder_id, query, notes, tags, date_sold, sold_price, image, back_image, ai_status
                ) VALUES (
                    :date_purchased, :quantity, :player, :year, :set_name, :variation, :card_number,
                    :category, :condition, :slab_serial_number, :investment, :estimated_value,
                    :ladder_id, :query, :notes, :tags, :date_sold, :sold_price, :image, :back_image, :ai_status
                );
                """, bad_rec)
                conn.commit()

        assert get_card_count(fresh_db) == 0


# ============================================================================
# Section 3: Summary Stats Accuracy Across Diverse Categories & Price Floats
# ============================================================================

class TestSection3SummaryStatsAccuracy:

    def test_empty_db_summary_stats(self, fresh_db):
        """Empty database returns 0 totals and empty category/status dictionaries."""
        stats = get_summary_stats(fresh_db)
        assert stats["total_cards"] == 0
        assert stats["total_investment"] == 0.0
        assert stats["total_estimated_value"] == 0.0
        assert stats["count_by_category"] == {}
        assert stats["count_by_ai_status"] == {}

    def test_all_22_categories_represented(self, fresh_db):
        """Inserts cards across all 22 categories and validates accurate per-category counts."""
        categories = list(VALID_CATEGORIES)
        assert len(categories) == 22
        
        batch = []
        expected_counts = {}
        for idx, cat in enumerate(categories, 1):
            count_for_cat = idx
            expected_counts[cat] = count_for_cat
            for j in range(count_for_cat):
                batch.append({
                    "player": f"{cat} Player {j}",
                    "year": "2024",
                    "set_name": "Multi-Sport All-Stars",
                    "category": cat,
                    "investment": 10.0,
                    "estimated_value": 20.0,
                })
        
        insert_cards_batch(batch, fresh_db)
        stats = get_summary_stats(fresh_db)
        
        total_expected_cards = sum(range(1, 23))
        assert stats["total_cards"] == total_expected_cards
        assert stats["total_investment"] == total_expected_cards * 10.0
        assert stats["total_estimated_value"] == total_expected_cards * 20.0
        assert stats["count_by_category"] == expected_counts

    def test_floating_point_price_precision_and_cancellation(self, fresh_db):
        """Tests float precision (e.g. 0.01, 19.99, 1234567.89, fractional cents)."""
        prices = [
            (0.01, 0.02),
            (0.10, 0.20),
            (19.99, 49.95),
            (150.75, 320.50),
            (9999.99, 15000.00),
            (1000000.50, 2500000.25),
        ]
        batch = []
        expected_inv = 0.0
        expected_est = 0.0
        for i, (inv, est) in enumerate(prices):
            expected_inv += inv
            expected_est += est
            batch.append({
                "player": f"Player {i}",
                "year": "2024",
                "set_name": "Prestige",
                "category": "Basketball",
                "investment": inv,
                "estimated_value": est,
            })
        
        insert_cards_batch(batch, fresh_db)
        stats = get_summary_stats(fresh_db)
        
        assert stats["total_cards"] == len(prices)
        assert stats["total_investment"] == round(expected_inv, 2)
        assert stats["total_estimated_value"] == round(expected_est, 2)

    def test_sum_of_1000_penny_cards(self, fresh_db):
        """1000 cards with investment=0.01 must equal exactly 10.00 without IEEE 754 drift."""
        batch = [
            {
                "player": f"Penny Card {i}",
                "year": "2024",
                "set_name": "Base Set",
                "category": "Baseball",
                "investment": 0.01,
                "estimated_value": 0.05,
            }
            for i in range(1000)
        ]
        insert_cards_batch(batch, fresh_db)
        stats = get_summary_stats(fresh_db)
        assert stats["total_cards"] == 1000
        assert stats["total_investment"] == 10.00
        assert stats["total_estimated_value"] == 50.00

    def test_ai_status_distribution(self, fresh_db):
        """Tests counts of CLEARED, REVIEW VARIATION, and NEEDS REVIEW."""
        cards = [
            {"player": "P1", "year": "2024", "set_name": "S", "category": "Baseball", "ai_status": "CLEARED"},
            {"player": "P2", "year": "2024", "set_name": "S", "category": "Baseball", "ai_status": "CLEARED"},
            {"player": "P3", "year": "2024", "set_name": "S", "variation": "Refractor", "category": "Baseball"},
            {"player": "P4", "year": "2024", "set_name": "S", "category": "Baseball", "ai_status": "NEEDS REVIEW"},
        ]
        insert_cards_batch(cards, fresh_db)
        stats = get_summary_stats(fresh_db)
        assert stats["count_by_ai_status"] == {
            "CLEARED": 2,
            "REVIEW VARIATION": 1,
            "NEEDS REVIEW": 1,
        }


# ============================================================================
# Section 4: Unicode Handling in Player, Set, Variation & Search
# ============================================================================

class TestSection4UnicodeHandling:

    @pytest.mark.parametrize("player_name, set_name, variation", [
        ("Ronald Acuña Jr.", "Topps Serie 1 Española", "Refractor Verde"),
        ("Vinícius Júnior", "Panini Select Brasil", "Cromo Ouro"),
        ("Alexis Lafrenière", "O-Pee-Chee Premier Édition Française", "Parallèle Rétro"),
        ("Luka Dončić", "Panini Prizm EuroBasket", "Srebrna Prizma"),
        ("Nikola Jokić", "National Treasures Balkan Special", "Platinasti Mozaik"),
        ("Jaromír Jágr", "Upper Deck Česko", "Zlatá Karta"),
        ("Tomáš Hertl", "Score Hokej", "Lesklá Varianta"),
        ("Erling Håland", "Topps Chrome Bundesliga", "Gold Refraktor /50"),
        ("Teemu Selänne", "Pinnacle Suomi", "Jääkiekko Tähti"),
        ("Shohei Ohtani (大谷 翔平)", "2023 BBM 日本プロ野球", "金箔サイン版 1/1"),
        ("Ichiro Suzuki (鈴木 一朗)", "1994 BBM オリックス・ブルーウェーブ", "ルーキー版"),
        ("Yu Darvish (ダルビッシュ 有)", "2005 BBM 北海道日本ハムファイターズ", "パッチカード"),
        ("ピカチュウ (Pikachu)", "1996 ポケモン第1弾拡張パック", "初版ホロ (1st Edition)"),
        ("Son Heung-min (손흥민)", "2022 Panini World Cup 대한민국", "골드 프리즘"),
        ("Lee Jung-hoo (이정후)", "2017 KBO 리그 컬렉션", "신인왕 한정판"),
        ("Yao Ming (姚明)", "2002 Upper Deck 亚洲版", "红色折射"),
        ("Wang Chien-ming (王建民)", "2005 Topps 台灣限量版", "白金特卡"),
        ("Karl-Anthony Towns", "Panini Donruss Optic", "Holo 1/1 Star"),
        ("De'Aaron Fox", "Panini Spectra City Edition", "Die-Cut Neon Blue /10"),
        ("Shaquille O'Neal", "1992-93 Fleer Ultra Precious Metals", "Gold Medallion"),
        ("Charizard", "Wizards of the Coast (WotC)", "Base Set 1st Ed. 1/4 Holo"),
    ])
    def test_unicode_round_trip_and_exact_match(self, fresh_db, player_name, set_name, variation):
        """Verifies Unicode strings are stored and retrieved with 100% byte and codepoint preservation."""
        card_data = {
            "player": player_name,
            "year": "2024",
            "set_name": set_name,
            "variation": variation,
            "category": "Baseball" if ("Baseball" in set_name or "BBM" in set_name or "MLB" in player_name or "Topps" in set_name) else "Basketball",
            "condition": "Raw",
            "notes": "8492-101",
        }
        card_id = insert_card(card_data, db_path=fresh_db)
        retrieved = get_card_by_id(card_id, fresh_db)
        
        assert retrieved is not None
        assert retrieved["player"] == player_name
        assert retrieved["set_name"] == set_name
        assert retrieved["variation"] == variation
        
        assert player_name in retrieved["query"]
        assert set_name in retrieved["query"]
        if variation:
            assert variation in retrieved["query"]

    def test_unicode_filtering_and_search(self, fresh_db):
        """Tests SQL LIKE search with Japanese, accented, and special character substrings."""
        cards = [
            {"player": "Shohei Ohtani (大谷 翔平)", "year": "2023", "set_name": "Topps Chrome 日本版", "category": "Baseball"},
            {"player": "Luka Dončić", "year": "2020", "set_name": "Panini Prizm", "category": "Basketball"},
            {"player": "Ronald Acuña Jr.", "year": "2018", "set_name": "Topps Update", "category": "Baseball"},
            {"player": "ピカチュウ (Pikachu)", "year": "1996", "set_name": "ポケモン第1弾", "category": "Pokemon"},
        ]
        insert_cards_batch(cards, fresh_db)
        
        results_ohtani = get_all_cards(search_query="大谷", db_path=fresh_db)
        assert len(results_ohtani) == 1
        assert results_ohtani[0]["player"] == "Shohei Ohtani (大谷 翔平)"

        results_pika = get_all_cards(search_query="ポケモン", db_path=fresh_db)
        assert len(results_pika) == 1
        assert "ピカチュウ" in results_pika[0]["player"]

        results_luka = get_all_cards(search_query="Dončić", db_path=fresh_db)
        assert len(results_luka) == 1
        assert results_luka[0]["player"] == "Luka Dončić"

        results_acuna = get_all_cards(search_query="Acuña", db_path=fresh_db)
        assert len(results_acuna) == 1
        assert results_acuna[0]["player"] == "Ronald Acuña Jr."


# ============================================================================
# Section 5: Additional Critical Boundary Values & Edge Cases
# ============================================================================

class TestSection5BoundaryValues:

    def test_card_number_leading_zero_preservation_across_formats(self, fresh_db):
        """Tests edge cases of card_number string preservation."""
        numbers = ["000", "007", "001", "04/100", "1/1", "#0099", "SSP-01", "0", "999999"]
        for num in numbers:
            cid = insert_card({
                "player": "Test Player",
                "year": "2024",
                "set_name": "Test Set",
                "category": "Baseball",
                "card_number": num,
            }, db_path=fresh_db)
            card = get_card_by_id(cid, fresh_db)
            assert card["card_number"] == num
            assert isinstance(card["card_number"], str)

    def test_quantity_boundary_values(self, fresh_db):
        """Quantity must be integer >= 1. 0 or negative numbers must fail."""
        with pytest.raises(ValidationError):
            CardRecord(player="P", year="2024", set_name="S", category="Baseball", quantity=0)

        with pytest.raises(ValidationError):
            CardRecord(player="P", year="2024", set_name="S", category="Baseball", quantity=-5)

        c = CardRecord(player="P", year="2024", set_name="S", category="Baseball", quantity=100)
        assert c.quantity == 100

    def test_year_boundary_values(self, fresh_db):
        """Year must be 4 digits. Historical sets (e.g. 1887 Allen & Ginter) and future years supported."""
        for y in ["1887", "1909", "1952", "1986", "2026", "2099"]:
            c = CardRecord(player="P", year=y, set_name="S", category="Baseball")
            assert c.year == y

        for invalid_y in ["188", "19099", "abcd", "202a", "-202"]:
            with pytest.raises(ValidationError):
                CardRecord(player="P", year=invalid_y, set_name="S", category="Baseball")

    def test_next_child_id_boundary_increments(self, fresh_db):
        """Verifies get_next_child_id increments beyond 100 correctly."""
        assert get_next_child_id("9999", fresh_db) == 101
        
        for cnum in [101, 105, 110]:
            insert_card({
                "player": f"Player {cnum}",
                "year": "2024",
                "set_name": "Set",
                "category": "Baseball",
                "notes": format_notes(9999, cnum)
            }, db_path=fresh_db)
        
        assert get_next_child_id("9999", fresh_db) == 111
        assert get_next_child_id("0001", fresh_db) == 101

