"""
test_edge_cases.py - Stress testing scraper edge cases, malformed HTML, Cardboard Connection formats,
and network offline fallbacks.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import patch, MagicMock
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "sports_cards", "ecosystem_hub")))

from models import CardExtractionSchema, CardRecord, AIStatus
from test_scraper_engine import (
    ChecklistHTMLParser,
    parse_checklist_html,
    parse_checklist_line,
    parse_checklist_table_row,
    expand_parallels,
    infer_metadata_from_text,
)


def test_cardboard_connection_list_format():
    cbc_html = """
    <!DOCTYPE html>
    <html>
    <head><title>2023 Panini Prizm Football Checklist</title></head>
    <body>
      <div class="entry-content">
        <h1>2023 Panini Prizm Football Checklist</h1>
        <h2>Base Set Checklist</h2>
        <ul>
          <li>1 Patrick Mahomes - Kansas City Chiefs</li>
          <li>007 Justin Jefferson - Minnesota Vikings</li>
          <li>101 C.J. Stroud, Houston Texans RC</li>
          <li>102 Bryce Young - Carolina Panthers (RC)</li>
          <li>103 Anthony Richardson [RC] - Indianapolis Colts</li>
          <li>BCP-1 Brock Purdy - San Francisco 49ers</li>
          <li>NNO Checklist Header Card</li>
        </ul>
      </div>
    </body>
    </html>
    """
    cards = parse_checklist_html(cbc_html, parallels=["Base"])
    assert len(cards) >= 6
    card_map = {c.card_number: c for c in cards}

    assert "007" in card_map
    assert card_map["007"].player == "Justin Jefferson"
    assert card_map["007"].card_number == "007"

    assert "101" in card_map
    assert card_map["101"].player == "C.J. Stroud"

    assert "102" in card_map
    assert card_map["102"].player == "Bryce Young"

    assert "BCP-1" in card_map
    assert card_map["BCP-1"].player == "Brock Purdy"

    print("Cardboard connection list format passed!")


def test_malformed_html_resilience():
    malformed_html = """
    <h1>2022 Topps Chrome Baseball Checklist
    <table>
      <tr><th>#<th>Player<th>Team
      <tr><td>01<td>Aaron Judge<td>New York Yankees
      <tr><td>007<td>Shohei Ohtani<td>Los Angeles Angels
      <tr><td>101<td>Adley Rutschman RC<td>Baltimore Orioles
    """ # Intentionally unclosed tags
    cards = parse_checklist_html(malformed_html, parallels=["Base"])
    assert len(cards) == 3
    assert cards[0].card_number == "01"
    assert cards[1].card_number == "007"
    assert cards[2].card_number == "101"
    print("Malformed HTML resilience passed!")


def test_empty_and_garbage_html():
    empty_cards = parse_checklist_html("<html><body><p>No cards here</p></body></html>", parallels=["Base"])
    assert len(empty_cards) == 0

    garbage_cards = parse_checklist_html("Just a plain string with no html tags", parallels=["Base"])
    assert len(garbage_cards) == 0
    print("Empty and garbage HTML passed!")


def test_network_offline_fallback():
    def fetch_and_parse(url: str, fallback_html: str = "") -> list[CardExtractionSchema]:
        try:
            resp = requests.get(url, timeout=2.0)
            resp.raise_for_status()
            return parse_checklist_html(resp.text)
        except Exception:
            if fallback_html:
                return parse_checklist_html(fallback_html)
            return []

    # Test with network error mock
    fallback = "<h1>2024 Panini Prizm Basketball</h1><table><tr><td>01</td><td>Victor Wembanyama</td><td>Spurs</td></tr></table>"
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Offline")):
        cards = fetch_and_parse("https://beckett.com/offline-url", fallback_html=fallback)
        assert len(cards) == 1
        assert cards[0].player == "Victor Wembanyama"
    print("Network offline fallback passed!")


if __name__ == "__main__":
    test_cardboard_connection_list_format()
    test_malformed_html_resilience()
    test_empty_and_garbage_html()
    test_network_offline_fallback()
    print("ALL EDGE CASE TESTS PASSED!")
