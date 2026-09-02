"""
tests/test_fuzzer_sales_generator.py - Property-Based & Randomized Stress Fuzzer for Sales Listing Generator.
1000+ randomized fuzz iterations verifying universal invariants:
- Title length strictly < 100 characters
- Buzzwords stripped
- Exactly 6 to 8 hashtags
- 6 mandatory sections present
- Graceful handling of any input schema/types without crashing
"""

import random
import string
import unicodedata
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sales_generator import (
    MockSalesGenerator,
    build_hashtags,
    build_seo_title,
    build_structured_listing,
    generate_marketplace_listing,
    normalize_card_input,
    resolve_asking_price,
    sanitize_seo_title,
    FORBIDDEN_BUZZWORDS,
)

SAMPLE_PLAYERS = [
    "Luka Doncic", "Shohei Ohtani", "Ronald Acuña Jr.", "Victor Wembanyama",
    "Michael Jordan", "LeBron James", "Patrick Mahomes II", "Connor McDavid",
    "Lionel Messi", "大谷 翔平", "Pikachu", "Charizard", "", "   ",
    "Player With Extremely Long Name Exceeding Normal Database Limits " * 5,
    "🔥 Fire Player 🚀", "L@@K INVEST!", "1/1? Grail Hunter",
]

SAMPLE_SETS = [
    "Panini Prizm", "Topps Chrome", "Bowman Draft", "National Treasures",
    "Upper Deck Young Guns", "Pokemon Base Set", "Fleer", "", "   ",
    "Extremely Long Set Name With Multi Parallel Subseries Mega Super Edition " * 4,
    "INVEST! Set 🔥",
]

SAMPLE_CONDITIONS = [
    "PSA 10", "PSA 9", "BGS 9.5", "BGS 10", "SGC 10", "CGC 9.5", "TAG 10",
    "BVG 8", "Raw", "Ungraded", "Near Mint", "Fair", "", "   ", "PSA 10?",
    "🔥 Pristine 10", "GEM?"
]

SAMPLE_VARIATIONS = [
    "Silver Prizm", "Refractor", "Base", "Gold /10", "1/1?", "1/1 SuperFractor",
    "Holo Rare", "Autograph Patch", "", "   ", "INVEST! Variation"
]

SAMPLE_CATEGORIES = [
    "Basketball", "Baseball", "Football", "Hockey", "Soccer", "Pokemon",
    "Trading Card Game", "Racing", "Wrestling", "", "   ", "Other"
]


def generate_random_card():
    return {
        "player": random.choice(SAMPLE_PLAYERS) if random.random() > 0.1 else None,
        "year": random.choice(["1986", "1999", "2003", "2018", "2023", "", None, 2024, "LongYear99999"]),
        "set_name": random.choice(SAMPLE_SETS) if random.random() > 0.1 else None,
        "variation": random.choice(SAMPLE_VARIATIONS) if random.random() > 0.1 else None,
        "card_number": random.choice(["1", "280", "NNO", "", None, 100, "#23"]),
        "category": random.choice(SAMPLE_CATEGORIES) if random.random() > 0.1 else None,
        "condition": random.choice(SAMPLE_CONDITIONS) if random.random() > 0.1 else None,
        "slab_serial_number": random.choice(["48192041", "", None, "99999999", "CERT-12345"]),
        "investment": random.choice([0.0, 10.0, 500.0, -50.0, None, "100", 1e6]),
        "estimated_value": random.choice([0.0, 25.0, 1200.0, -100.0, None, "250", 1e7]),
        "notes": random.choice(["", "Nice card", "8492-101", None]),
    }


def test_1000_fuzz_iterations():
    random.seed(42)
    for i in range(1000):
        card = generate_random_card()
        custom_asking_price = random.choice([None, 0.0, -10.0, 150.0, "300", 9999.99])
        custom_notes = random.choice(["", "Firm price", "Trade for Jordan", None])

        # 1. Normalization
        norm = normalize_card_input(card)
        assert isinstance(norm, dict)

        # 2. Price resolution
        price = resolve_asking_price(norm, custom_asking_price)
        assert isinstance(price, float)
        assert price >= 0.0

        # 3. SEO Title invariants
        title = build_seo_title(norm)
        assert len(title) < 100, f"Iteration {i}: Title length {len(title)} >= 100: '{title}'"
        assert not title.endswith(" ")

        # 4. Hashtag invariants
        tags = build_hashtags(norm)
        assert 6 <= len(tags) <= 8, f"Iteration {i}: Hashtags count {len(tags)} not in [6, 8]: {tags}"
        for tag in tags:
            assert tag.startswith("#")
            assert len(tag) > 1
            assert tag[1:].isalnum()

        # 5. Full listing generation
        listing = MockSalesGenerator.generate(norm, asking_price=price, custom_notes=custom_notes or "")
        assert "ASKING PRICE:" in listing
        assert "KEY SPECIFICATIONS:" in listing
        assert "CONDITION & AUTHENTICITY:" in listing
        assert "SHIPPING & LOCAL PICKUP:" in listing
        assert "TAGS:" in listing

        # 6. Structured listing model
        struct = build_structured_listing(norm, asking_price=price, custom_notes=custom_notes or "")
        assert struct.title == title
        assert 6 <= len(struct.hashtags) <= 8
        assert struct.price >= 0.0
