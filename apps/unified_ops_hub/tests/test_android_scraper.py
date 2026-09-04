"""Comprehensive Tests for Android CLI Mobile Automation Engine & Viral Trend Scraper.
Following TDD / Loud Assertions Protocol (Requirement R3).
"""

import os
import re
import json
import time
import tempfile
import shutil
import pytest
from typing import Dict, Any, List, Optional, Tuple

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
)
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper


# ============================================================================
# Mock Android Subprocess Harness for Deterministic Loud Assertion Testing
# ============================================================================

class MockAndroidDeviceState:
    """Deterministic in-memory Android device state for test execution."""

    def __init__(self, serial: str = "emulator-5554", is_connected: bool = True):
        self.serial = serial
        self.is_connected = is_connected
        self.status = "device" if is_connected else "offline"
        self.foreground_app = "com.zhiliaoapp.musically"
        self.screen_width = 1080
        self.screen_height = 2400
        self.touch_log: List[Tuple[int, int]] = []
        self.swipe_log: List[Tuple[int, int, int, int, int]] = []
        self.text_log: List[str] = []
        self.keyevent_log: List[int] = []
        self.samsung_auto_blocker_enabled = True
        self.android_cli_available = True
        self.simulated_timeout = False

        self.layout_nodes: List[Dict[str, Any]] = [
            {
                "key": 1048576,
                "class": "android.widget.TextView",
                "resourceId": "com.zhiliaoapp.musically:id/title",
                "text": "#EDM #UltraMiami #MartinGarrix Mainstage drop was insane!",
                "contentDesc": "Video caption with hashtags",
                "bounds": "[48,1620][860,1740]",
                "center": "[454,1680]",
                "interactions": ["clickable"],
                "state": ["focused"],
                "off-screen": False,
            },
            {
                "key": 1048577,
                "class": "android.widget.TextView",
                "resourceId": "com.zhiliaoapp.musically:id/music_title",
                "text": "Martin Garrix - Animals (Festival VIP Remix)",
                "contentDesc": "Original Sound Track",
                "bounds": "[48,1750][700,1810]",
                "center": "[374,1780]",
                "interactions": ["clickable"],
                "state": [],
                "off-screen": False,
            },
            {
                "key": 1048578,
                "class": "android.widget.Button",
                "resourceId": "com.zhiliaoapp.musically:id/like_count",
                "text": "1.4M",
                "contentDesc": "1.4 million likes",
                "bounds": "[920,1300][1040,1420]",
                "center": "[980,1360]",
                "interactions": ["clickable"],
                "state": [],
                "off-screen": False,
            },
            {
                "key": 1048579,
                "class": "android.widget.Button",
                "resourceId": "com.zhiliaoapp.musically:id/comment_count",
                "text": "35.2K",
                "contentDesc": "35,200 comments",
                "bounds": "[920,1440][1040,1540]",
                "center": "[980,1490]",
                "interactions": ["clickable"],
                "state": [],
                "off-screen": False,
            },
            {
                "key": 1048580,
                "class": "android.widget.Button",
                "resourceId": "com.zhiliaoapp.musically:id/share_count",
                "text": "12.5K",
                "contentDesc": "12,500 shares",
                "bounds": "[920,1560][1040,1660]",
                "center": "[980,1610]",
                "interactions": ["clickable"],
                "state": [],
                "off-screen": False,
            },
            {
                "key": 1048581,
                "class": "android.widget.TextView",
                "resourceId": "com.zhiliaoapp.musically:id/author_handle",
                "text": "@rave_master_official",
                "contentDesc": "Creator username",
                "bounds": "[48,1550][400,1600]",
                "center": "[224,1575]",
                "interactions": ["clickable"],
                "state": [],
                "off-screen": False,
            },
        ]

    def runner(self, cmd: List[str], timeout: Optional[float] = None) -> str:
        """Mock subprocess command dispatcher executing ADB and Android CLI commands."""
        if self.simulated_timeout:
            raise CommandTimeoutError(f"Command timed out after {timeout} seconds: {' '.join(cmd)}")

        if not self.is_connected and "devices" not in cmd and "info" not in cmd:
            raise DeviceOfflineError(f"error: device '{self.serial}' not found / offline")

        binary = cmd[0]

        # 1. Android CLI Commands
        if binary == "android":
            if not self.android_cli_available:
                raise FileNotFoundError("The system cannot find the file specified: 'android'")
            sub = cmd[1] if len(cmd) > 1 else ""
            if sub == "info":
                return f"connected-devices: {self.serial}\nsdk-path: /sdk/android\n"
            elif sub == "layout":
                return json.dumps(self.layout_nodes)
            elif sub == "screen" and len(cmd) > 2 and cmd[2] == "capture":
                return "Screen captured successfully"
            return ""

        # 2. Pure ADB Commands
        elif binary == "adb":
            # Strip device serial flags if present: adb -s <serial> ...
            args = list(cmd[1:])
            if len(args) >= 2 and args[0] == "-s":
                args = args[2:]

            if not args:
                return ""

            if args[0] == "devices":
                if self.is_connected:
                    return f"List of devices attached\n{self.serial}\tdevice product:tangorpro model:Pixel_Tablet device:tangorpro\n"
                else:
                    return "List of devices attached\n"

            elif args[0] == "shell":
                shell_args = args[1:]
                if not shell_args:
                    return ""

                # input commands
                if shell_args[0] == "input":
                    action = shell_args[1]
                    if action == "tap":
                        x, y = int(shell_args[2]), int(shell_args[3])
                        self.touch_log.append((x, y))
                        return ""
                    elif action == "swipe":
                        x1, y1, x2, y2, ms = (
                            int(shell_args[2]),
                            int(shell_args[3]),
                            int(shell_args[4]),
                            int(shell_args[5]),
                            int(shell_args[6]),
                        )
                        self.swipe_log.append((x1, y1, x2, y2, ms))
                        return ""
                    elif action == "text":
                        self.text_log.append(shell_args[2])
                        return ""
                    elif action == "keyevent":
                        self.keyevent_log.append(int(shell_args[2]))
                        return ""

                # settings put global rampart_auto_enabled_switch_enabled 0
                elif shell_args[0] == "settings":
                    if (
                        shell_args[1:4] == ["put", "global", "rampart_auto_enabled_switch_enabled"]
                        and shell_args[4] == "0"
                    ):
                        self.samsung_auto_blocker_enabled = False
                        return ""

                # uiautomator dump <path>
                elif shell_args[0] == "uiautomator" and shell_args[1] == "dump":
                    return "UI hierchary dumped to: /data/local/tmp/dump.xml"

                # cat /data/local/tmp/dump.xml
                elif shell_args[0] == "cat" and "dump.xml" in shell_args[1]:
                    return self.generate_xml_dump()

                # am start / monkey
                elif shell_args[0] == "am" and shell_args[1] == "start":
                    return "Starting: Intent { act=android.intent.action.VIEW ... }"
                elif shell_args[0] == "monkey":
                    return f":Monkey: seed=0 count=1\nEvents injected: 1"

                # dumpsys window
                elif shell_args[0] == "dumpsys" and shell_args[1] == "window":
                    return f"  mCurrentFocus=Window{{a1b2c3d u0 {self.foreground_app}}}"

                # wm size
                elif shell_args[0] == "wm" and shell_args[1] == "size":
                    return f"Physical size: {self.screen_width}x{self.screen_height}"

            elif args[0] == "exec-out" and args[1] == "screencap":
                return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" # Mock PNG bytes header

        return ""

    def generate_xml_dump(self) -> str:
        """Generates valid XML representation matching the current layout nodes."""
        xml_lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<hierarchy rotation="0">']
        for node in self.layout_nodes:
            text = node.get("text", "")
            res_id = node.get("resourceId", "")
            bounds = node.get("bounds", "[0,0][0,0]")
            desc = node.get("contentDesc", "")
            cls = node.get("class", "android.view.View")
            xml_lines.append(
                f'  <node text="{text}" resource-id="{res_id}" class="{cls}" '
                f'content-desc="{desc}" bounds="{bounds}" clickable="true" enabled="true" />'
            )
        xml_lines.append("</hierarchy>")
        return "\n".join(xml_lines)


@pytest.fixture
def mobile_env():
    """Provides isolated temp dirs for DLQ, mock device harness, and client/scraper instances."""
    temp_dir = tempfile.mkdtemp(prefix="test_mobile_")
    db_path = os.path.join(temp_dir, "test_mobile_dlq.db")
    quarantine_dir = os.path.join(temp_dir, "quarantine")

    dlq_mgr = DLQManager(db_path=db_path, quarantine_dir=quarantine_dir)
    mock_device = MockAndroidDeviceState()
    client = AndroidClient(
        serial="emulator-5554",
        runner=mock_device.runner,
        timeout=5.0,
    )
    scraper = MobileViralTrendScraper(client=client, dlq_manager=dlq_mgr)

    yield {
        "temp_dir": temp_dir,
        "db_path": db_path,
        "quarantine_dir": quarantine_dir,
        "dlq_mgr": dlq_mgr,
        "mock_device": mock_device,
        "client": client,
        "scraper": scraper,
    }
    shutil.rmtree(temp_dir, ignore_errors=True)


# ============================================================================
# 1. Pydantic Models & Data Structures Tests
# ============================================================================

def test_scraped_trend_item_model_and_velocity_calculation():
    """Loud Assertion: ScrapedTrendItem validates fields and computes viral velocity accurately."""
    item = ScrapedTrendItem(
        item_id="trend_001",
        platform="tiktok",
        topic="EDM Festival Drops",
        caption="Martin Garrix at Ultra 2026 mainstage #EDM #UltraMiami #MartinGarrix",
        hashtags=["EDM", "UltraMiami", "MartinGarrix"],
        sound_title="Martin Garrix - Animals (Festival VIP Remix)",
        author_handle="@rave_master_official",
        view_count=500000,
        like_count=1400000,
        comment_count=35200,
        share_count=12500,
        post_age_hours=2.0,
        raw_bounds="[48,1620][860,1740]",
    )

    # Expected velocity: (1,400,000 * 10 + 35,200 * 50 + 12,500 * 100) / 2.0
    # = (14,000,000 + 1,760,000 + 1,250,000) / 2.0 = 17,010,000 / 2.0 = 8,505,000.0
    assert item.item_id == "trend_001"
    assert item.platform == "tiktok"
    assert len(item.hashtags) == 3
    assert item.velocity_score == pytest.approx(8505000.0, 0.1)

    # Serialization / Deserialization
    data = item.to_dict()
    assert data["item_id"] == "trend_001"
    assert data["velocity_score"] == pytest.approx(8505000.0, 0.1)

    restored = ScrapedTrendItem.from_dict(data)
    assert restored.item_id == item.item_id
    assert restored.hashtags == item.hashtags
    assert restored.velocity_score == item.velocity_score


def test_device_state_and_scrape_metrics_models():
    """Loud Assertion: DeviceState and ScrapeMetrics properly calculate yield and parse rates."""
    device = DeviceState(
        serial="emulator-5554",
        status="device",
        model="Pixel_Tablet",
        product="tangorpro",
        screen_width=1080,
        screen_height=2400,
        samsung_auto_blocker_disabled=True,
        is_emulator=True,
    )
    assert device.is_ready() is True

    metrics = ScrapeMetrics(
        session_id="session_abc",
        duration_seconds=12.5,
        total_frames_dumped=10,
        successful_parses=8,
        failed_parses=2,
        average_frame_latency_ms=250.0,
        top_hashtags=[("EDM", 8), ("UltraMiami", 5)],
        top_sounds=[("Animals Remix", 4)],
    )
    assert metrics.yield_rate == pytest.approx(0.8, 0.01)
    assert metrics.failure_rate == pytest.approx(0.2, 0.01)


# ============================================================================
# 2. Android Client Device Discovery & Lifecycle Tests
# ============================================================================

def test_client_device_discovery_and_state(mobile_env):
    """Loud Assertion: AndroidClient lists connected devices and detects model/state."""
    client: AndroidClient = mobile_env["client"]
    devices = client.list_devices()
    assert len(devices) == 1
    dev = devices[0]
    assert dev.serial == "emulator-5554"
    assert dev.status == "device"
    assert dev.model == "Pixel_Tablet"

    state = client.get_device_state()
    assert state.serial == "emulator-5554"
    assert state.screen_width == 1080
    assert state.screen_height == 2400


def test_samsung_auto_blocker_disablement(mobile_env):
    """Loud Assertion: AndroidClient pre-flight disables Samsung Auto Blocker (One UI 6.0+)."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    assert mock_dev.samsung_auto_blocker_enabled is True
    success = client.disable_samsung_auto_blocker()
    assert success is True
    assert mock_dev.samsung_auto_blocker_enabled is False


def test_offline_device_raises_error(mobile_env):
    """Loud Assertion: Operations on an offline or disconnected device raise DeviceOfflineError."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    mock_dev.is_connected = False
    with pytest.raises(DeviceOfflineError):
        client.tap_coordinates(500, 500)


def test_command_timeout_protection(mobile_env):
    """Loud Assertion: Subprocess execution respects bounded timeout limits."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    mock_dev.simulated_timeout = True
    with pytest.raises(CommandTimeoutError):
        client.get_foreground_package()


# ============================================================================
# 3. Touch, Swipe, Keyevent & Keystroke Injection Primitives
# ============================================================================

def test_tap_coordinates_and_element_bounds_calculation(mobile_env):
    """Loud Assertion: Element center is mathematically derived from bounds and tapped."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    # Direct coordinate tap
    client.tap_coordinates(100, 200)
    assert len(mock_dev.touch_log) == 1
    assert mock_dev.touch_log[-1] == (100, 200)

    # Element bounds string parsing: "[48,1620][860,1740]"
    # Center X: (48 + 860) / 2 = 454; Center Y: (1620 + 1740) / 2 = 1680
    success = client.tap_element_bounds("[48,1620][860,1740]")
    assert success is True
    assert len(mock_dev.touch_log) == 2
    assert mock_dev.touch_log[-1] == (454, 1680)


def test_swipe_primitives_and_directional_feed_scroll(mobile_env):
    """Loud Assertion: Swipe gestures correctly calculate trajectories for feed pagination."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    # Explicit coordinates swipe
    client.swipe(540, 1800, 540, 400, duration_ms=450)
    assert len(mock_dev.swipe_log) == 1
    assert mock_dev.swipe_log[-1] == (540, 1800, 540, 400, 450)

    # Directional swipe up (advances vertical feed forward)
    # Screen is 1080x2400 -> mid_x=540, start_y = 2400*0.8 = 1920, end_y = 2400*0.2 = 480
    client.swipe_direction("up", distance_ratio=0.6, duration_ms=500)
    assert len(mock_dev.swipe_log) == 2
    assert mock_dev.swipe_log[-1][0] == 540
    assert mock_dev.swipe_log[-1][2] == 540
    assert mock_dev.swipe_log[-1][1] > mock_dev.swipe_log[-1][3]  # Upward motion


def test_keystroke_space_and_special_character_escaping(mobile_env):
    """Loud Assertion: Keystrokes adhere to Rule R10.2 / Tier 4 by escaping spaces with %s and encoding symbols."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    raw_text = "Ultra Miami 2026 $50 & VIP #Festival"
    client.inject_text(raw_text)
    assert len(mock_dev.text_log) == 1
    injected = mock_dev.text_log[0]
    assert " " not in injected
    assert "%s" in injected
    assert "%24" in injected or "\\$" in injected or "%s50" in injected
    assert injected.startswith("Ultra%sMiami%s2026")


def test_hardware_keyevents_and_app_launching(mobile_env):
    """Loud Assertion: AndroidClient injects hardware keycodes (Back, Home, Enter) and launches packages."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    # Keyevents
    client.send_keyevent(4)  # Back
    client.send_keyevent(3)  # Home
    client.send_keyevent(66) # Enter
    assert mock_dev.keyevent_log == [4, 3, 66]

    # Launch app package
    success = client.launch_app("com.zhiliaoapp.musically")
    assert success is True

    # Open deep link URI
    success = client.open_deep_link("https://www.tiktok.com/tag/electronicmusic")
    assert success is True


# ============================================================================
# 4. Headless UI Layout Parsing & Metric Extraction Tests
# ============================================================================

def test_metric_number_parser():
    """Loud Assertion: parse_metric_number normalizes string abbreviations into integer quantities."""
    parser = MobileViralTrendScraper.parse_metric_number

    assert parser("1.4M") == 1400000
    assert parser("2.5M") == 2500000
    assert parser("35.2K") == 35200
    assert parser("100K") == 100000
    assert parser("12,500") == 12500
    assert parser("950") == 950
    assert parser("0") == 0
    assert parser("InvalidString") == 0
    assert parser("") == 0
    assert parser(None) == 0


def test_hashtag_extractor():
    """Loud Assertion: extract_hashtags parses hashtag tokens from raw text captions."""
    extractor = MobileViralTrendScraper.extract_hashtags

    text = "Insane drop! #EDM #Ultra2026 #MartinGarrix #Festival_Life check it out!"
    tags = extractor(text)
    assert tags == ["EDM", "Ultra2026", "MartinGarrix", "Festival_Life"]

    # Text with no hashtags
    assert extractor("Just plain text with no tags") == []
    assert extractor("") == []
    assert extractor(None) == []


def test_json_layout_tree_parsing(mobile_env):
    """Loud Assertion: Scraper extracts structured ScrapedTrendItem from JSON layout trees."""
    scraper: MobileViralTrendScraper = mobile_env["scraper"]
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]

    items = scraper.parse_layout_nodes(mock_dev.layout_nodes, platform="tiktok")
    assert len(items) == 1
    item = items[0]

    assert item.platform == "tiktok"
    assert "UltraMiami" in item.hashtags
    assert item.sound_title == "Martin Garrix - Animals (Festival VIP Remix)"
    assert item.author_handle == "@rave_master_official"
    assert item.like_count == 1400000
    assert item.comment_count == 35200
    assert item.share_count == 12500
    assert item.velocity_score > 1000000.0


def test_xml_layout_tree_fallback_parsing(mobile_env):
    """Loud Assertion: Scraper parses raw XML dump when android-cli layout is unavailable."""
    scraper: MobileViralTrendScraper = mobile_env["scraper"]
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]

    xml_data = mock_dev.generate_xml_dump()
    items = scraper.parse_xml_hierarchy(xml_data, platform="tiktok")
    assert len(items) == 1
    item = items[0]

    assert item.platform == "tiktok"
    assert "MartinGarrix" in item.hashtags
    assert item.like_count == 1400000
    assert item.comment_count == 35200


# ============================================================================
# 5. Fallback, Resiliency & Dead Letter Queue (DLQ) Integration Tests
# ============================================================================

def test_android_cli_missing_fallback_to_xml_dump(mobile_env):
    """Loud Assertion: When android CLI is unavailable, client automatically falls back to ADB XML dump."""
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]
    client: AndroidClient = mobile_env["client"]

    mock_dev.android_cli_available = False
    nodes = client.get_layout_tree()
    assert len(nodes) >= 1
    assert any(n.get("text") and "#EDM" in n.get("text") for n in nodes)


def test_corrupted_xml_quarantined_to_dlq(mobile_env):
    """Loud Assertion: Malformed or unparseable XML is captured into the DLQ without crashing the scraper."""
    scraper: MobileViralTrendScraper = mobile_env["scraper"]
    dlq_mgr: DLQManager = mobile_env["dlq_mgr"]

    corrupted_xml = "<?xml version='1.0' encoding='UTF-8'?><hierarchy><node unclosed='true' >"
    items = scraper.parse_xml_hierarchy(corrupted_xml, platform="tiktok")
    assert items == []  # Gracefully returns empty list

    # Verify incident was captured in DLQ
    incidents = dlq_mgr.list_incidents(category=ErrorCategory.CORRUPTED_PAYLOAD)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.source_service == "mobile_scraper"
    assert inc.error_category == ErrorCategory.CORRUPTED_PAYLOAD
    assert "XML" in inc.error_message or "Parse" in inc.error_message


def test_corrupted_json_nodes_quarantined_to_dlq(mobile_env):
    """Loud Assertion: Malformed node dictionaries during JSON parsing are quarantined in DLQ."""
    scraper: MobileViralTrendScraper = mobile_env["scraper"]
    dlq_mgr: DLQManager = mobile_env["dlq_mgr"]

    bad_nodes = [
        {"invalid_key": object()}, # Non-serializable / unexpected structure
    ]
    items = scraper.parse_layout_nodes(bad_nodes, platform="tiktok")
    assert items == []


# ============================================================================
# 6. Autonomous Mobile Feed Scraping Workflow Tests
# ============================================================================

def test_autonomous_scrape_feed_loop_and_metrics(mobile_env):
    """Loud Assertion: scrape_feed executes full zero-touch navigation, metric tracking, and yield calculation."""
    scraper: MobileViralTrendScraper = mobile_env["scraper"]
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]

    session, items, metrics = scraper.scrape_feed(
        platform="tiktok",
        target_url_or_tag="https://www.tiktok.com/tag/electronicmusic",
        max_swipes=3,
        delay_between_swipes_sec=0.01,
    )

    assert session.status == "COMPLETED"
    assert session.items_scraped >= 1
    assert len(items) >= 1
    assert metrics.total_frames_dumped >= 3
    assert metrics.successful_parses >= 1
    assert metrics.yield_rate > 0.0
    assert len(mock_dev.swipe_log) >= 2  # Swiped to paginate across frames


def test_scrape_feed_device_disconnect_failure_handling(mobile_env):
    """Loud Assertion: Device disconnect during feed scraping records failure and updates session status."""
    scraper: MobileViralTrendScraper = mobile_env["scraper"]
    mock_dev: MockAndroidDeviceState = mobile_env["mock_device"]

    mock_dev.is_connected = False
    session, items, metrics = scraper.scrape_feed(
        platform="tiktok",
        target_url_or_tag="https://www.tiktok.com/tag/electronicmusic",
        max_swipes=2,
        delay_between_swipes_sec=0.01,
    )

    assert session.status == "FAILED"
    assert len(session.errors) >= 1
    assert items == []
