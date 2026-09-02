"""Adversarial and Empirical Stress Test Suite for Android CLI Mobile Automation Engine.
Tests AndroidClient and MobileViralTrendScraper against:
- Malformed and pathological XML UI trees (unclosed tags, XML injection, invalid characters, null bytes, huge entity payloads)
- Deeply nested layouts (150+ levels), massive trees (10,000+ nodes)
- Unicode, multilingual, emoji-heavy captions, RTL text, invisible chars, special symbols
- Metric parsing boundary conditions (overflows, malformed formats, empty/null, trailing garbage, negatives)
- Hashtag extractor boundary cases (numbers, symbols, unicode, case-preservation, consecutive hashes)
- Touch/Swipe/Gesture coordinate calculations (negative, inverted, out-of-bound, invalid bounds strings)
- Samsung Auto Blocker, app launching, intent deep-linking, keyevents
- Device timeout simulations, sudden disconnects, unhandled process terminations
- Dead Letter Queue (DLQ) quarantine verification (ensuring 0 crashes, proper ErrorCategory, complete payload logging)
- Concurrency & multithreaded stress testing
"""

import os
import json
import time
import tempfile
import shutil
import threading
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple
import pytest

from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory, IncidentStatus
from unified_ops_hub.mobile.models import (
    ScrapedTrendItem,
    DeviceState,
    MobileScrapeSession,
    ScrapeMetrics,
)
from unified_ops_hub.mobile.android_client import (
    AndroidClient,
    AndroidAutomationError,
    DeviceNotFoundError,
    DeviceOfflineError,
    CommandTimeoutError,
    UIAutomatorError,
)
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper


class MockAdversarialDevice:
    """Mock device for simulating extreme adversarial and fault conditions."""

    def __init__(self, serial: str = "emulator-5554"):
        self.serial = serial
        self.is_connected = True
        self.raise_timeout = False
        self.raise_offline = False
        self.raise_not_found = False
        self.raise_process_error = False
        self.return_corrupt_output = False
        self.custom_xml = None
        self.custom_nodes = None
        self.calls: List[List[str]] = []
        self.screen_width = 1080
        self.screen_height = 2400
        self.auto_blocker_disabled = False

    def runner(self, cmd: List[str], timeout: Optional[float] = None) -> Any:
        self.calls.append(cmd)

        if self.raise_timeout:
            raise CommandTimeoutError(f"Simulated timeout after {timeout}s: {' '.join(cmd)}")
        if self.raise_offline:
            raise DeviceOfflineError(f"error: device '{self.serial}' is offline")
        if self.raise_not_found:
            raise DeviceNotFoundError(f"error: device '{self.serial}' not found")
        if self.raise_process_error:
            raise RuntimeError("Subprocess terminated unexpectedly with SIGKILL")

        binary = cmd[0]

        if binary == "android":
            if cmd[1:2] == ["layout"]:
                if self.return_corrupt_output:
                    return "INVALID_JSON_NON_PARSEABLE_{{{["
                if self.custom_nodes is not None:
                    return json.dumps(self.custom_nodes)
                return "[]"
            return ""

        if binary == "adb":
            args = list(cmd[1:])
            if len(args) >= 2 and args[0] == "-s":
                args = args[2:]

            if not args:
                return ""

            if args[0] == "devices":
                if self.is_connected:
                    return f"List of devices attached\n{self.serial}\tdevice product:tangorpro model:Pixel_Tablet\n"
                return "List of devices attached\n"

            if args[0] == "shell":
                shell_args = args[1:]
                if not shell_args:
                    return ""

                if shell_args[0] == "wm" and shell_args[1] == "size":
                    return f"Physical size: {self.screen_width}x{self.screen_height}"

                if shell_args[0] == "dumpsys" and shell_args[1] == "window":
                    return "  mCurrentFocus=Window{123 u0 com.zhiliaoapp.musically}"

                if shell_args[0] == "settings":
                    self.auto_blocker_disabled = True
                    return ""

                if shell_args[0] == "cat" and "dump.xml" in shell_args[1]:
                    if self.custom_xml is not None:
                        return self.custom_xml
                    return '<?xml version="1.0"?><hierarchy></hierarchy>'

                if shell_args[0] == "uiautomator" and shell_args[1] == "dump":
                    return "UI hierchary dumped to: /data/local/tmp/dump.xml"

                if shell_args[0] == "input":
                    return ""

            if args[0] == "exec-out" and args[1] == "screencap":
                return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"

        return ""


@pytest.fixture
def adversarial_env():
    temp_dir = tempfile.mkdtemp(prefix="adv_mobile_test_")
    db_path = os.path.join(temp_dir, "adv_dlq.db")
    quarantine_dir = os.path.join(temp_dir, "quarantine")

    dlq_mgr = DLQManager(db_path=db_path, quarantine_dir=quarantine_dir)
    mock_dev = MockAdversarialDevice()
    client = AndroidClient(serial="emulator-5554", runner=mock_dev.runner, timeout=2.0)
    scraper = MobileViralTrendScraper(client=client, dlq_manager=dlq_mgr)

    yield {
        "temp_dir": temp_dir,
        "dlq_mgr": dlq_mgr,
        "mock_dev": mock_dev,
        "client": client,
        "scraper": scraper,
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# 1. Malformed & Pathological XML Stress Tests
# ============================================================================

def test_adversarial_xml_truncated_and_unclosed_tags(adversarial_env):
    """Stress-test truncated, unclosed, and syntactically broken XML trees."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]
    dlq_mgr: DLQManager = adversarial_env["dlq_mgr"]

    bad_xmls = [
        "<?xml version='1.0'?><hierarchy><node bounds='[0,0][100,100]'",
        "<hierarchy><node text='test'><unclosed>",
        "<?xml><hierarchy><node text='foo'></node></wrong_root>",
        "<<<<>>>>",
        "",
        "   \n\t  ",
        "<html><body>Not an Android XML hierarchy</body></html>",
        "{'json': 'instead_of_xml'}",
        "<?xml version='1.0' encoding='UTF-8'?><hierarchy><node text='Unescaped & in text' bounds='[0,0][10,10]' /></hierarchy>",
        "\x00\x01\x02\x03\x04\x05",
        "<?xml version='1.0'?>\n<!DOCTYPE foo [\n  <!ELEMENT foo ANY >\n  <!ENTITY xxe SYSTEM 'file:///etc/passwd' >]>\n<foo>&xxe;</foo>",
    ]

    for bad_xml in bad_xmls:
        result = scraper.parse_xml_hierarchy(bad_xml, platform="tiktok")
        # Must not crash, must return empty list on malformed / unparseable
        assert isinstance(result, list)

    incidents = dlq_mgr.list_incidents(category=ErrorCategory.CORRUPTED_PAYLOAD)
    assert len(incidents) >= 7, "Malformed XML must be captured in DLQ"
    for inc in incidents:
        assert inc.source_service == "mobile_scraper"
        assert inc.status == IncidentStatus.QUARANTINED
        assert "raw_xml_snippet" in inc.payload


def test_adversarial_xml_missing_attributes_and_malformed_bounds(adversarial_env):
    """Test XML nodes with missing required attributes, malformed bounds, and weird tags."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]

    xml_with_odd_nodes = """<?xml version="1.0" encoding="UTF-8"?>
    <hierarchy rotation="0">
      <node />
      <node text="" />
      <node text="#ValidTag Great track!" bounds="INVALID_BOUNDS_FORMAT" resource-id="com.app:id/title" />
      <node bounds="[abc,def][ghi,jkl]" text="Another text #SecondTag" resource-id="com.app:id/desc" />
      <node bounds="[-100,-200][500,600]" text="Negative bounds #Cool" resource-id="com.app:id/caption" />
    </hierarchy>
    """
    items = scraper.parse_xml_hierarchy(xml_with_odd_nodes, platform="instagram")
    assert len(items) == 1
    item = items[0]
    assert any(tag in item.hashtags for tag in ["ValidTag", "SecondTag", "Cool"])
    assert item.platform == "instagram"


def test_adversarial_deeply_nested_xml_hierarchy(adversarial_env):
    """Stress-test deep recursion in XML trees (150 nested levels)."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]

    # Construct 150 nested levels of nodes
    nested_xml = '<?xml version="1.0" encoding="UTF-8"?>\n<hierarchy rotation="0">\n'
    depth = 150
    for i in range(depth):
        nested_xml += f'  <node class="android.widget.FrameLayout" index="{i}">\n'
    nested_xml += '    <node text="Deep nested caption #Ultra2026 #EDM" resource-id="com.app:id/title" bounds="[0,0][1080,2400]" />\n'
    nested_xml += '    <node text="1.5M" resource-id="com.app:id/like_count" bounds="[0,0][100,100]" />\n'
    for _ in range(depth):
        nested_xml += '  </node>\n'
    nested_xml += '</hierarchy>'

    items = scraper.parse_xml_hierarchy(nested_xml, platform="tiktok")
    assert len(items) == 1
    assert items[0].like_count == 1500000
    assert "Ultra2026" in items[0].hashtags


def test_adversarial_massive_node_tree_performance(adversarial_env):
    """Stress-test layout tree parsing with 10,000 nodes for memory and latency safety."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]

    # Create 10,000 noise nodes plus 1 viral trend node
    massive_nodes = []
    for i in range(10000):
        massive_nodes.append({
            "key": i,
            "class": "android.view.View",
            "resourceId": f"com.app:id/dummy_{i}",
            "text": f"Noise string {i}",
            "contentDesc": f"Desc {i}",
            "bounds": "[0,0][10,10]",
        })
    massive_nodes.append({
        "key": 99999,
        "class": "android.widget.TextView",
        "resourceId": "com.app:id/title",
        "text": "Viral anthem of the year! #FestivalVibes #Summer2026",
        "contentDesc": "Video caption",
        "bounds": "[50,1500][800,1650]",
    })
    massive_nodes.append({
        "key": 100000,
        "class": "android.widget.Button",
        "resourceId": "com.app:id/like_count",
        "text": "2.8M",
        "contentDesc": "Likes",
        "bounds": "[900,1200][1000,1300]",
    })

    t0 = time.time()
    items = scraper.parse_layout_nodes(massive_nodes, platform="tiktok")
    duration = time.time() - t0

    assert len(items) == 1
    assert items[0].like_count == 2800000
    assert "FestivalVibes" in items[0].hashtags
    assert duration < 1.0, f"Parsing 10k nodes took {duration:.3f}s, expected < 1.0s"


# ============================================================================
# 2. Unicode, Emojis, RTL & Special Content Stress Tests
# ============================================================================

def test_adversarial_unicode_and_emojis_in_captions_and_sounds(adversarial_env):
    """Test unicode characters, emoji strings, multi-byte encodings, and RTL text."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]

    nodes = [
        {
            "key": 1,
            "resourceId": "com.zhiliaoapp.musically:id/title",
            "text": "🔥🚀🎧 AMAZING DROP! 💥✨ #UltraMiami2026 #EDM_Life #HardTechno 🎶🎹",
            "bounds": "[48,1620][860,1740]",
        },
        {
            "key": 2,
            "resourceId": "com.zhiliaoapp.musically:id/music_title",
            "text": "🎵 Tiësto & Martin Garrix — The Only Way Is UP (Remix) 🎧",
            "bounds": "[48,1750][700,1810]",
        },
        {
            "key": 3,
            "resourceId": "com.zhiliaoapp.musically:id/author_handle",
            "text": "@dj_tësto_official",
            "bounds": "[48,1550][400,1600]",
        },
        {
            "key": 4,
            "resourceId": "com.zhiliaoapp.musically:id/like_count",
            "text": "3.5M",
            "bounds": "[920,1300][1040,1420]",
        },
    ]

    items = scraper.parse_layout_nodes(nodes, platform="tiktok")
    assert len(items) == 1
    item = items[0]
    assert "UltraMiami2026" in item.hashtags
    assert "EDM_Life" in item.hashtags
    assert "HardTechno" in item.hashtags
    assert "Tiësto" in item.sound_title
    assert "🔥" in item.caption
    assert item.like_count == 3500000
    assert item.author_handle == "@dj_tësto_official"


def test_adversarial_non_ascii_and_control_characters(adversarial_env):
    """Test captions containing null bytes, ANSI escapes, newlines, and zero-width spaces."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]

    weird_caption = "Line1\nLine2\r\n\t\x1b[31mRedText\x1b[0m \u200B\u200C #TechnoDrop #Rave2026 \u0000Null"
    nodes = [
        {
            "key": 1,
            "resourceId": "com.app:id/caption",
            "text": weird_caption,
            "bounds": "[0,0][100,100]",
        }
    ]

    items = scraper.parse_layout_nodes(nodes, platform="tiktok")
    assert len(items) == 1
    item = items[0]
    assert "TechnoDrop" in item.hashtags
    assert "Rave2026" in item.hashtags


def test_adversarial_huge_caption_string(adversarial_env):
    """Test extremely large caption string (100,000 characters) doesn't cause crash or ReDoS."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]

    huge_text = "word " * 20000 + "#MassiveTag #EndTag"
    nodes = [
        {
            "key": 1,
            "resourceId": "com.app:id/caption",
            "text": huge_text,
            "bounds": "[0,0][1080,2400]",
        }
    ]

    t0 = time.time()
    items = scraper.parse_layout_nodes(nodes, platform="tiktok")
    duration = time.time() - t0

    assert len(items) == 1
    assert "MassiveTag" in items[0].hashtags
    assert "EndTag" in items[0].hashtags
    assert duration < 0.5


# ============================================================================
# 3. Metric Parser & Hashtag Extractor Boundary Conditions
# ============================================================================

@pytest.mark.parametrize(
    "input_str,expected",
    [
        ("1.4M", 1400000),
        ("2.55M", 2550000),
        ("35.2K", 35200),
        ("0.5K", 500),
        ("100K", 100000),
        ("1.2B", 1200000000),
        ("12,500", 12500),
        ("1,400,000", 1400000),
        ("950", 950),
        ("0", 0),
        ("0.0", 0),
        ("0K", 0),
        ("0.00M", 0),
        ("", 0),
        ("   ", 0),
        (None, 0),
        ("Invalid", 0),
        ("--", 0),
        ("N/A", 0),
        ("1.4.5M", 0),         # Malformed float gracefully returns 0
        ("  1.4 M ", 1400000), # Whitespace inside
        ("35.2k", 35200),     # Lowercase k
        ("1.8m", 1800000),   # Lowercase m
        ("2.1b", 2100000000), # Lowercase b
        ("+50K", 50000),      # Plus sign stripped
        ("999999999", 999999999),
        ("-500", 500),        # Strips non-digit/matches digits
    ],
)
def test_parse_metric_number_exhaustive_boundaries(input_str, expected):
    """Exhaustive boundary testing for metric number parser."""
    assert MobileViralTrendScraper.parse_metric_number(input_str) == expected


@pytest.mark.parametrize(
    "caption_text,expected_tags",
    [
        ("#EDM #Ultra #2026", ["EDM", "Ultra", "2026"]),
        ("#tag_with_underscore #tag-with-dash", ["tag_with_underscore", "tag"]), # Dash splits regex
        ("No tags in this string at all", []),
        ("###MultipleHashes", ["MultipleHashes"]),
        ("#1 #2 #3", ["1", "2", "3"]),
        ("#CardLadder #SportsCards #ToppsChrome", ["CardLadder", "SportsCards", "ToppsChrome"]),
        (None, []),
        ("", []),
        ("#", []),
        ("#   #", []),
        ("#tag1#tag2#tag3", ["tag1", "tag2", "tag3"]),
    ],
)
def test_extract_hashtags_exhaustive_boundaries(caption_text, expected_tags):
    """Exhaustive boundary testing for hashtag regex extraction."""
    assert MobileViralTrendScraper.extract_hashtags(caption_text) == expected_tags


# ============================================================================
# 4. Android Client Gesture Coordinates & String Encoding Boundary Tests
# ============================================================================

def test_android_client_tap_bounds_parsing_adversarial(adversarial_env):
    """Test tap_element_bounds with valid, invalid, inverted, and malformed strings."""
    client: AndroidClient = adversarial_env["client"]
    mock_dev: MockAdversarialDevice = adversarial_env["mock_dev"]

    # 1. Valid standard bounds
    assert client.tap_element_bounds("[0,0][100,200]") is True
    # 2. Inverted bounds: [100,200][0,0] -> Center ((100+0)//2, (200+0)//2) = (50, 100)
    assert client.tap_element_bounds("[100,200][0,0]") is True
    # 3. Invalid format bounds strings must return False and NOT crash
    assert client.tap_element_bounds("INVALID") is False
    assert client.tap_element_bounds("") is False
    assert client.tap_element_bounds("[0,0]") is False
    assert client.tap_element_bounds("[a,b][c,d]") is False
    assert client.tap_element_bounds("0,0,100,100") is False


def test_android_client_swipe_direction_unsupported(adversarial_env):
    """Test swipe_direction raises ValueError on invalid direction."""
    client: AndroidClient = adversarial_env["client"]
    with pytest.raises(ValueError, match="Unsupported swipe direction"):
        client.swipe_direction("diagonal_up_left")


def test_android_client_text_injection_escaping(adversarial_env):
    """Test text injection properly escapes spaces and special characters for ADB input."""
    client: AndroidClient = adversarial_env["client"]
    mock_dev: MockAdversarialDevice = adversarial_env["mock_dev"]

    client.inject_text("Hello World & Peace $100 #Viral")
    # Verify escaped string
    calls = [c for c in mock_dev.calls if "input" in c and "text" in c]
    assert len(calls) == 1
    arg = calls[0][-1]
    assert " " not in arg
    assert "%s" in arg
    assert "%26" in arg
    assert "%24" in arg
    assert "%23" in arg


# ============================================================================
# 5. Device Fault Injection, Timeouts & Disconnection Handling
# ============================================================================

def test_scrape_feed_handles_mid_scrape_device_disconnect(adversarial_env):
    """Test fault tolerance when device disconnects on the 2nd swipe of a 5-swipe scrape session."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]
    mock_dev: MockAdversarialDevice = adversarial_env["mock_dev"]
    dlq_mgr: DLQManager = adversarial_env["dlq_mgr"]

    # Provide initial valid node layout for swipe 1
    mock_dev.custom_nodes = [
        {
            "key": 1,
            "resourceId": "com.app:id/title",
            "text": "Initial post before disconnect #EDM",
            "bounds": "[0,0][100,100]",
        }
    ]

    # Custom runner that works on first call and throws on subsequent swipe
    call_count = 0
    orig_runner = mock_dev.runner

    def flaky_runner(cmd: List[str], timeout: Optional[float] = None):
        nonlocal call_count
        call_count += 1
        if call_count > 4:  # After pre-flight and 1st layout fetch
            raise DeviceOfflineError("device disconnected abruptly via ADB transport")
        return orig_runner(cmd, timeout)

    scraper.client._custom_runner = flaky_runner

    session, items, metrics = scraper.scrape_feed(
        platform="tiktok",
        max_swipes=5,
        delay_between_swipes_sec=0.01,
    )

    # Session must be marked FAILED without crashing the daemon
    assert session.status == "FAILED"
    assert len(session.errors) >= 1
    assert "disconnected" in session.errors[0]

    # DLQ must have logged the timeout/disconnect failure
    incidents = dlq_mgr.list_incidents(category=ErrorCategory.TIMEOUT)
    assert len(incidents) >= 1
    assert "disconnected" in incidents[0].error_message


def test_scrape_feed_handles_device_not_found_exception(adversarial_env):
    """Test scraper handling of non-existent device serial."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]
    mock_dev: MockAdversarialDevice = adversarial_env["mock_dev"]
    dlq_mgr: DLQManager = adversarial_env["dlq_mgr"]

    mock_dev.raise_not_found = True

    session, items, metrics = scraper.scrape_feed(
        platform="instagram",
        max_swipes=2,
        delay_between_swipes_sec=0.01,
    )

    assert session.status == "FAILED"
    assert len(session.errors) >= 1
    assert items == []

    incidents = dlq_mgr.list_incidents()
    assert len(incidents) >= 1


def test_scrape_feed_handles_subprocess_crash(adversarial_env):
    """Test scraper handling of sudden subprocess crash (SIGKILL/Exception)."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]
    mock_dev: MockAdversarialDevice = adversarial_env["mock_dev"]

    mock_dev.raise_process_error = True

    session, items, metrics = scraper.scrape_feed(
        platform="youtube",
        max_swipes=2,
        delay_between_swipes_sec=0.01,
    )

    assert session.status == "FAILED"
    assert len(session.errors) >= 1
    assert "SIGKILL" in session.errors[0] or "terminated" in session.errors[0]


def test_corrupted_json_payload_sanitization_in_dlq(adversarial_env):
    """Test that malformed/non-JSON-serializable objects in layout nodes are sanitized before DLQ write."""
    scraper: MobileViralTrendScraper = adversarial_env["scraper"]
    dlq_mgr: DLQManager = adversarial_env["dlq_mgr"]

    class UnserializableObject:
        def __repr__(self):
            return "<CustomUnserializableObject>"

    corrupted_nodes = [
        {
            "key": 1,
            "resourceId": "com.app:id/title",
            "text": "Bad node payload",
            "bad_field": UnserializableObject(),
        },
        "Not even a dictionary",
    ]

    items = scraper.parse_layout_nodes(corrupted_nodes, platform="tiktok")
    assert items == []

    # Verify DLQ received sanitized payload and did not raise TypeError on json.dumps
    incidents = dlq_mgr.list_incidents(category=ErrorCategory.CORRUPTED_PAYLOAD)
    assert len(incidents) >= 1
    inc = incidents[0]
    assert inc.source_service == "mobile_scraper"
    assert "nodes_sample" in inc.payload


# ============================================================================
# 6. Concurrency and Thread-Safety Stress Testing
# ============================================================================

def test_multithreaded_concurrent_scraping_and_dlq_recording(adversarial_env):
    """Stress-test concurrent scrape runs and simultaneous DLQ error recordings."""
    dlq_mgr: DLQManager = adversarial_env["dlq_mgr"]

    errors: List[Exception] = []

    def worker_task(thread_id: int):
        try:
            local_mock = MockAdversarialDevice(serial=f"emulator-555{thread_id}")
            local_client = AndroidClient(
                serial=f"emulator-555{thread_id}",
                runner=local_mock.runner,
                timeout=3.0
            )
            local_scraper = MobileViralTrendScraper(client=local_client, dlq_manager=dlq_mgr)

            # Alternate between valid, malformed XML, and corrupt JSON nodes
            if thread_id % 3 == 0:
                local_scraper.parse_xml_hierarchy("<<<broken>>>", platform="tiktok")
            elif thread_id % 3 == 1:
                local_scraper.parse_layout_nodes([123, 456], platform="instagram")
            else:
                session, items, metrics = local_scraper.scrape_feed(platform="youtube", max_swipes=2, delay_between_swipes_sec=0.0)
                assert session.status == "COMPLETED"
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(15)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0, f"Thread errors occurred: {errors}"
    stats = dlq_mgr.get_stats()
    assert stats["total_incidents"] >= 10, "All error threads must be recorded safely in DLQ"


# ============================================================================
# 7. Velocity Score Mathematical Precision & Stress
# ============================================================================

def test_velocity_score_near_zero_age_and_large_numbers():
    """Verify velocity score calculation avoids ZeroDivisionError and handles integer overflow."""
    # Near-zero post age (0.01h)
    item_zero_age = ScrapedTrendItem(
        platform="tiktok",
        caption="Breaking drop #EDM",
        like_count=1000,
        comment_count=50,
        share_count=20,
        post_age_hours=0.0, # Will be clamped to >= 0.1
    )
    # Expected: (1000*10 + 50*50 + 20*100) / 0.1 = (10000 + 2500 + 2000) / 0.1 = 14500 / 0.1 = 145,000.0
    assert item_zero_age.velocity_score == pytest.approx(145000.0, 0.1)

    # Massive numbers
    item_huge = ScrapedTrendItem(
        platform="tiktok",
        caption="Mega viral #Viral",
        like_count=50_000_000,
        comment_count=2_000_000,
        share_count=1_000_000,
        post_age_hours=24.0,
    )
    # Expected: (50M*10 + 2M*50 + 1M*100) / 24 = (500M + 100M + 100M) / 24 = 700,000,000 / 24 = 29,166,666.67
    assert item_huge.velocity_score == pytest.approx(29166666.67, 1.0)
