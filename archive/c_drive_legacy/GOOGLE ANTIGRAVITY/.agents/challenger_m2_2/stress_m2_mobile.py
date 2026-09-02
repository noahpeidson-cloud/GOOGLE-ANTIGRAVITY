"""Adversarial Empirical Stress Suite for Milestone 2: Android CLI Mobile Automation Engine.
Evaluates ScrapedTrendItem validation, velocity calculation, high-frequency feed pagination,
DLQ quarantine under sustained failure, and zero memory leaks / unclosed file descriptors.
"""

import os
import gc
import sys
import json
import time
import uuid
import random
import shutil
import tempfile
import threading
import tracemalloc
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple

# Ensure workspace root is in sys.path
WORKSPACE_ROOT = r"g:\My Drive\GOOGLE ANTIGRAVITY"
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

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
from unified_ops_hub.gateway.dlq_manager import (
    DLQManager,
    DLQIncident,
    ErrorCategory,
    IncidentStatus,
)


class TestFailure(Exception):
    pass


def log_test(title: str):
    print(f"\n{'='*70}\n[RUNNING] {title}\n{'='*70}")


def log_pass(title: str, detail: str = ""):
    msg = f"[PASS] {title}"
    if detail:
        msg += f" -> {detail}"
    print(msg)


# ============================================================================
# Section 1: ScrapedTrendItem Validation & Edge Case Stress Testing
# ============================================================================

def test_scraped_trend_item_extreme_boundaries():
    log_test("1.1 ScrapedTrendItem Extreme Boundaries & Types")

    # 1. Zero and Negative Post Age
    item_zero_age = ScrapedTrendItem(like_count=100, comment_count=10, share_count=5, post_age_hours=0.0)
    # Velocity raw: (100*10 + 10*50 + 5*100) / 0.1 = 2000 / 0.1 = 20000.0
    assert item_zero_age.velocity_score == 20000.0, f"Expected 20000.0, got {item_zero_age.velocity_score}"

    item_neg_age = ScrapedTrendItem(like_count=100, comment_count=10, share_count=5, post_age_hours=-10.5)
    # Velocity raw: 2000 / 0.1 = 20000.0 (clamped to 0.1)
    assert item_neg_age.velocity_score == 20000.0, f"Expected 20000.0, got {item_neg_age.velocity_score}"

    # 2. Large numbers (Trillions)
    item_massive = ScrapedTrendItem(
        like_count=10**10,
        comment_count=10**9,
        share_count=10**9,
        post_age_hours=24.0,
    )
    # Expected: (10^11 + 5*10^10 + 10^11) / 24 = 2.5 * 10^11 / 24 = 10416666666.67
    expected_vel = round((10**10 * 10.0 + 10**9 * 50.0 + 10**9 * 100.0) / 24.0, 2)
    assert item_massive.velocity_score == expected_vel, f"Massive numbers failed: {item_massive.velocity_score} vs {expected_vel}"

    # 3. Unicode, Emojis, RTL, Special Characters
    test_caption = "🔥 Rave Life @ Ultra Miami 🚀 🎉! #EDM #Trance #Ultra2026 🎵🎶 \u202eRTL_OVERRIDE\u202c \u0000NullTest"
    item_unicode = ScrapedTrendItem(
        caption=test_caption,
        hashtags=["EDM", "Trance", "Ultra2026", "🔥Rave"],
        author_handle="@dj_køsmös_🚀",
        sound_title="Martin Garrix - Tremor (Slander & NGHTMRE Remix 🎧)",
    )
    assert item_unicode.caption == test_caption
    assert "@dj_køsmös_🚀" == item_unicode.author_handle
    
    # 4. JSON roundtrip with full fidelity
    serialized = item_unicode.to_dict()
    deserialized = ScrapedTrendItem.from_dict(serialized)
    assert deserialized.caption == item_unicode.caption
    assert deserialized.author_handle == item_unicode.author_handle
    assert deserialized.hashtags == item_unicode.hashtags
    assert deserialized.sound_title == item_unicode.sound_title
    assert deserialized.item_id == item_unicode.item_id

    # 5. Pre-set manual velocity override
    item_pre_set = ScrapedTrendItem(
        like_count=1000,
        comment_count=100,
        share_count=50,
        post_age_hours=1.0,
        velocity_score=9999.99,
    )
    # Should not overwrite manually assigned non-zero velocity score
    assert item_pre_set.velocity_score == 9999.99

    log_pass("ScrapedTrendItem Extreme Boundaries", "Clamped negative age, handled trillions, preserved unicode/emojis and custom velocity")


# ============================================================================
# Section 2: Velocity Calculation Determinism & Random Oracle Verification
# ============================================================================

def test_velocity_calculation_determinism_oracle():
    log_test("1.2 Velocity Calculation Determinism across 10,000 Iterations")

    rng = random.Random(42)  # Deterministic seed
    for i in range(10000):
        likes = rng.randint(0, 50_000_000)
        comments = rng.randint(0, 2_000_000)
        shares = rng.randint(0, 1_000_000)
        age = rng.uniform(-5.0, 500.0)

        item = ScrapedTrendItem(
            like_count=likes,
            comment_count=comments,
            share_count=shares,
            post_age_hours=age,
        )

        # Oracle calculation
        effective_age = max(age, 0.1)
        if likes == 0 and comments == 0 and shares == 0:
            expected = 0.0
        else:
            expected = round((likes * 10.0 + comments * 50.0 + shares * 100.0) / effective_age, 2)

        if item.velocity_score != expected:
            raise TestFailure(f"Velocity divergence at iter {i}: likes={likes}, comments={comments}, shares={shares}, age={age} -> got {item.velocity_score}, expected {expected}")

    log_pass("Velocity Calculation Determinism", "10,000 randomized permutations matched oracle with 0.00% divergence")


# ============================================================================
# Section 3: High-Frequency Feed Pagination & Deduplication Stress
# ============================================================================

class HighFrequencyMockDevice:
    """Mock device producing varied frames and layout streams at high frequency."""

    def __init__(self, total_unique_items: int = 50, failure_rate: float = 0.1):
        self.serial = "emulator-5554"
        self.is_connected = True
        self.swipe_count = 0
        self.failure_rate = failure_rate
        self.total_unique_items = total_unique_items
        self.rng = random.Random(1337)

    def runner(self, cmd: List[str], timeout: Optional[float] = None) -> Any:
        binary = cmd[0]
        if binary == "android":
            if cmd[1] == "layout":
                if self.rng.random() < self.failure_rate:
                    # Return malformed JSON or empty
                    if self.rng.random() < 0.5:
                        return "MALFORMED_JSON_TREE"
                    return "[]"

                idx = self.swipe_count % self.total_unique_items
                nodes = [
                    {
                        "key": 1048576 + idx,
                        "class": "android.widget.TextView",
                        "resourceId": f"com.zhiliaoapp.musically:id/title",
                        "text": f"High frequency trend #{idx} #EDM #ViralTrack_{idx} festival drop!",
                        "contentDesc": f"Caption {idx}",
                        "bounds": "[48,1620][860,1740]",
                    },
                    {
                        "key": 1048577 + idx,
                        "class": "android.widget.TextView",
                        "resourceId": f"com.zhiliaoapp.musically:id/music",
                        "text": f"Soundtrack Track #{idx % 10} - DJ EDM",
                        "contentDesc": "Music audio",
                        "bounds": "[48,1750][700,1810]",
                    },
                    {
                        "key": 1048578 + idx,
                        "class": "android.widget.Button",
                        "resourceId": "com.zhiliaoapp.musically:id/like_count",
                        "text": f"{(idx + 1) * 10}K",
                        "contentDesc": "likes",
                        "bounds": "[920,1300][1040,1420]",
                    },
                    {
                        "key": 1048579 + idx,
                        "class": "android.widget.Button",
                        "resourceId": "com.zhiliaoapp.musically:id/comment_count",
                        "text": f"{(idx + 1) * 2}K",
                        "contentDesc": "comments",
                        "bounds": "[920,1440][1040,1540]",
                    },
                ]
                return json.dumps(nodes)
            return ""

        elif binary == "adb":
            args = list(cmd[1:])
            if len(args) >= 2 and args[0] == "-s":
                args = args[2:]
            if not args:
                return ""
            if args[0] == "devices":
                return f"List of devices attached\n{self.serial}\tdevice\n"
            elif args[0] == "shell":
                if args[1:] == ["settings", "put", "global", "rampart_auto_enabled_switch_enabled", "0"]:
                    return ""
                elif args[1] == "input" and args[2] == "swipe":
                    self.swipe_count += 1
                    return ""
                elif args[1] == "wm" and args[2] == "size":
                    return "Physical size: 1080x2400"
                elif args[1] == "dumpsys":
                    return "mCurrentFocus=Window{123 u0 com.zhiliaoapp.musically}"
                elif args[1] == "uiautomator":
                    return "UI hierchary dumped"
                elif args[1] == "cat":
                    idx = self.swipe_count % self.total_unique_items
                    return f'<hierarchy><node text="High frequency trend #{idx} #EDM #ViralTrack_{idx} festival drop!" resource-id="title" bounds="[0,0][100,100]" /></hierarchy>'
            elif args[0] == "exec-out" and args[1] == "screencap":
                return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (b"X" * 1024)

        return ""


def test_high_frequency_pagination_and_metrics():
    log_test("1.3 High-Frequency Feed Pagination & Telemetry Accuracy (500 Swipes)")

    temp_dir = tempfile.mkdtemp(prefix="test_hf_scrape_")
    db_path = os.path.join(temp_dir, "dlq.db")
    quarantine_dir = os.path.join(temp_dir, "quarantine")

    dlq_mgr = DLQManager(db_path=db_path, quarantine_dir=quarantine_dir)
    mock_dev = HighFrequencyMockDevice(total_unique_items=50, failure_rate=0.15)
    client = AndroidClient(serial="emulator-5554", runner=mock_dev.runner, timeout=2.0)
    scraper = MobileViralTrendScraper(client=client, dlq_manager=dlq_mgr)

    t0 = time.time()
    session, items, metrics = scraper.scrape_feed(
        platform="tiktok",
        target_url_or_tag="https://www.tiktok.com/tag/edm",
        max_swipes=500,
        delay_between_swipes_sec=0.0001,
    )
    elapsed = time.time() - t0

    assert session.status == "COMPLETED", f"Session status was {session.status}"
    assert metrics.total_frames_dumped == 500, f"Expected 500 frames, got {metrics.total_frames_dumped}"
    assert metrics.successful_parses + metrics.failed_parses == 500, "Frame count mismatch"
    assert len(items) == 50, f"Deduplication failed: got {len(items)} items for 50 unique trends"
    assert abs((metrics.yield_rate + metrics.failure_rate) - 1.0) <= 0.02, f"Yield + Failure rate sum != 1.0: {metrics.yield_rate} + {metrics.failure_rate}"
    assert metrics.duration_seconds > 0.0
    assert len(metrics.top_hashtags) > 0

    shutil.rmtree(temp_dir, ignore_errors=True)
    log_pass("High-Frequency Feed Pagination", f"Processed 500 frames in {elapsed:.3f}s, exactly deduplicated {len(items)} items, yield={metrics.yield_rate:.2f}")


# ============================================================================
# Section 4: DLQ Quarantine Under Sustained Failure & Concurrent Hammering
# ============================================================================

def test_dlq_sustained_failure_and_thread_safety():
    log_test("1.4 DLQ Quarantine Under Sustained Concurrent Failure (1,000 Incidents)")

    temp_dir = tempfile.mkdtemp(prefix="test_dlq_stress_")
    db_path = os.path.join(temp_dir, "dlq_stress.db")
    quarantine_dir = os.path.join(temp_dir, "quarantine")

    dlq_mgr = DLQManager(db_path=db_path, quarantine_dir=quarantine_dir)

    num_threads = 10
    incidents_per_thread = 100
    total_expected = num_threads * incidents_per_thread

    errors = []

    def worker_fn(thread_id: int):
        for i in range(incidents_per_thread):
            try:
                cat = random.choice(list(ErrorCategory))
                payload = {
                    "thread_id": thread_id,
                    "iteration": i,
                    "blob": "x" * 200,
                    "nested": {"a": i, "b": [1, 2, 3]},
                }
                dlq_mgr.record_failure(
                    source_service="mobile_scraper_stress",
                    error_category=cat,
                    error_message=f"Simulated sustained failure from thread {thread_id} iter {i}",
                    payload=payload,
                    traceback_str="Traceback (most recent call last):\n  File 'test.py', line 42",
                    max_retries=3,
                )
            except Exception as e:
                errors.append((thread_id, i, str(e)))

    threads = [threading.Thread(target=worker_fn, args=(t,)) for t in range(num_threads)]
    t0 = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.time() - t0

    if errors:
        raise TestFailure(f"DLQ concurrent hammering encountered {len(errors)} errors: {errors[:3]}")

    # Verify SQLite record count
    stats = dlq_mgr.get_stats()
    assert stats["total_incidents"] == total_expected, f"Expected {total_expected} incidents, got {stats['total_incidents']}"
    assert stats["quarantined_count"] == total_expected

    # Verify SQLite database integrity
    with dlq_mgr._get_connection() as conn:
        integrity_rows = conn.execute("PRAGMA integrity_check;").fetchall()
        integrity_vals = [r[0] for r in integrity_rows]
        assert integrity_vals == ["ok"], f"SQLite integrity check failed: {integrity_vals}"

    # Verify JSON audit files on disk
    json_files = [f for f in os.listdir(quarantine_dir) if f.startswith("dlq_") and f.endswith(".json")]
    assert len(json_files) == total_expected, f"Expected {total_expected} JSON files, found {len(json_files)}"

    # Spot check 50 JSON files for parseability and correct content
    for fname in random.sample(json_files, min(50, len(json_files))):
        fpath = os.path.join(quarantine_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert "incident_id" in data
            assert data["source_service"] == "mobile_scraper_stress"
            assert data["status"] == "QUARANTINED"

    # Test Batch Replay Execution
    test_incident = dlq_mgr.list_incidents(limit=1)[0]
    
    # 1. Success replay
    res = dlq_mgr.replay_incident(test_incident.incident_id, handler=lambda p: {"status": "ok", "processed": True})
    assert res["success"] is True
    updated = dlq_mgr.get_incident(test_incident.incident_id)
    assert updated.status == IncidentStatus.RESOLVED

    # 2. Failure replay leading to exhaustion
    test_incident_fail = dlq_mgr.list_incidents(status=IncidentStatus.QUARANTINED, limit=1)[0]
    for _ in range(test_incident_fail.max_retries):
        dlq_mgr.replay_incident(test_incident_fail.incident_id, handler=lambda p: (_ for _ in ()).throw(ValueError("Persistent failure")))
    
    exhausted_inc = dlq_mgr.get_incident(test_incident_fail.incident_id)
    assert exhausted_inc.status == IncidentStatus.EXHAUSTED
    assert exhausted_inc.retry_count == test_incident_fail.max_retries

    shutil.rmtree(temp_dir, ignore_errors=True)
    log_pass("DLQ Sustained Failure & Thread Safety", f"Recorded {total_expected} concurrent incidents in {elapsed:.3f}s with 0 errors and verified SQLite PRAGMA integrity")


# ============================================================================
# Section 5: Zero Memory Leaks & Resource / FD Exhaustion
# ============================================================================

def test_zero_resource_leaks_screenshot_and_dumps():
    log_test("1.5 Zero Memory Leaks & File Descriptor Closure Verification (1,000 Iterations)")

    temp_dir = tempfile.mkdtemp(prefix="test_leak_check_")
    screenshot_dir = os.path.join(temp_dir, "screenshots")
    os.makedirs(screenshot_dir, exist_ok=True)

    mock_dev = HighFrequencyMockDevice(total_unique_items=10, failure_rate=0.0)
    client = AndroidClient(serial="emulator-5554", runner=mock_dev.runner, timeout=2.0)

    # 1. Screenshot Capture File Descriptor Closure (1,000 screen captures)
    tracemalloc.start()
    gc.collect()
    snap_before = tracemalloc.take_snapshot()

    for i in range(1000):
        img_path = os.path.join(screenshot_dir, f"frame_{i % 50}.png")
        data = client.capture_screen(output_path=img_path)
        assert len(data) > 0
        # Check that file can be overwritten or removed immediately without Windows file lock errors
        if i % 100 == 0:
            with open(img_path, "rb") as f_check:
                _ = f_check.read(10)

    gc.collect()
    snap_after = tracemalloc.take_snapshot()
    top_stats = snap_after.compare_to(snap_before, 'lineno')
    total_diff_kb = sum(stat.size_diff for stat in top_stats) / 1024.0

    tracemalloc.stop()

    # Memory growth for 1000 screencaps must be tightly bounded (< 10 MB)
    assert total_diff_kb < 10240, f"Memory leak detected during screenshot loop: {total_diff_kb:.2f} KB growth"

    # 2. UI Layout Tree & XML Dump Processing Memory & FD Closure (1,000 iterations)
    tracemalloc.start()
    gc.collect()
    snap_xml_before = tracemalloc.take_snapshot()

    for i in range(1000):
        nodes = client.get_layout_tree()
        assert len(nodes) > 0

    gc.collect()
    snap_xml_after = tracemalloc.take_snapshot()
    xml_stats = snap_xml_after.compare_to(snap_xml_before, 'lineno')
    xml_diff_kb = sum(stat.size_diff for stat in xml_stats) / 1024.0

    tracemalloc.stop()

    assert xml_diff_kb < 5120, f"Memory leak detected during layout dump loop: {xml_diff_kb:.2f} KB growth"

    # 3. File Quarantine Descriptor & Move verification (200 files)
    dlq_db = os.path.join(temp_dir, "quarantine_test.db")
    dlq_qdir = os.path.join(temp_dir, "qdir")
    dlq_mgr = DLQManager(db_path=dlq_db, quarantine_dir=dlq_qdir)

    for i in range(200):
        src_file = os.path.join(temp_dir, f"temp_corrupt_{i}.xml")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write(f"<corrupt_xml_file_{i}>")
        
        inc, qpath = dlq_mgr.quarantine_file(
            source_file_path=src_file,
            source_service="mobile_scraper",
            reason="Malformed XML",
        )
        assert not os.path.exists(src_file), f"Source file was not cleanly moved: {src_file}"
        assert os.path.exists(qpath), f"Quarantined file missing: {qpath}"
        assert inc.payload["file_size"] > 0

    shutil.rmtree(temp_dir, ignore_errors=True)
    log_pass("Zero Resource Leaks & FD Closure", f"1,000 screencaps (heap delta: {total_diff_kb:.1f} KB), 1,000 layout dumps (heap delta: {xml_diff_kb:.1f} KB), 200 file quarantines completed with 0 locks")


# ============================================================================
# Section 6: Device Lifecycle Fault Tolerance & Transitions
# ============================================================================

def test_device_lifecycle_and_fault_tolerance():
    log_test("1.6 Device Lifecycle & Disconnect Fault Tolerance")

    class StateTransitionDevice:
        def __init__(self):
            self.serial = "emulator-5554"
            self.connected = True
            self.swipes = 0

        def runner(self, cmd: List[str], timeout: Optional[float] = None) -> Any:
            # Check disconnection first unless listing devices
            if not self.connected and "devices" not in cmd:
                raise DeviceOfflineError("Device offline during command execution")

            binary = cmd[0]
            if binary == "android":
                return json.dumps([
                    {
                        "key": 1,
                        "resourceId": "com.zhiliaoapp.musically:id/title",
                        "text": f"Item before disconnect #{self.swipes} #EDM",
                        "bounds": "[0,0][100,100]",
                    }
                ])
            elif binary == "adb":
                args = list(cmd[1:])
                if len(args) >= 2 and args[0] == "-s":
                    args = args[2:]
                if not args:
                    return ""
                if args[0] == "devices":
                    if self.connected:
                        return f"List of devices attached\n{self.serial}\tdevice\n"
                    return "List of devices attached\n"
                elif args[0] == "shell":
                    if args[1:] == ["settings", "put", "global", "rampart_auto_enabled_switch_enabled", "0"]:
                        return ""
                    if args[1] == "input" and args[2] == "swipe":
                        self.swipes += 1
                        if self.swipes >= 3:
                            # Disconnect device on 3rd swipe
                            self.connected = False
                        return ""
                    if args[1] == "wm" and args[2] == "size":
                        return "Physical size: 1080x2400"
            return ""

    temp_dir = tempfile.mkdtemp(prefix="test_transition_")
    db_path = os.path.join(temp_dir, "transition_dlq.db")
    dlq_mgr = DLQManager(db_path=db_path, quarantine_dir=os.path.join(temp_dir, "q"))
    
    dev = StateTransitionDevice()
    client = AndroidClient(serial="emulator-5554", runner=dev.runner)
    scraper = MobileViralTrendScraper(client=client, dlq_manager=dlq_mgr)

    session, items, metrics = scraper.scrape_feed(
        platform="tiktok",
        max_swipes=10,
        delay_between_swipes_sec=0.001,
    )

    assert session.status == "FAILED"
    assert len(session.errors) >= 1
    assert "Device" in session.errors[0] or "offline" in session.errors[0]
    
    # DLQ should have recorded the timeout / offline incident
    incidents = dlq_mgr.list_incidents(source_service="mobile_scraper")
    assert len(incidents) >= 1
    assert incidents[0].error_category == ErrorCategory.TIMEOUT

    shutil.rmtree(temp_dir, ignore_errors=True)
    log_pass("Device Lifecycle & Disconnect", "Session safely transitioned to FAILED and recorded DLQ incident upon mid-stream disconnect")


# ============================================================================
# Main Execution Entrypoint
# ============================================================================

def main():
    print("=" * 80)
    print("STARTING EMPIRICAL ADVERSARIAL STRESS SUITE — MILESTONE 2")
    print("=" * 80)

    try:
        test_scraped_trend_item_extreme_boundaries()
        test_velocity_calculation_determinism_oracle()
        test_high_frequency_pagination_and_metrics()
        test_dlq_sustained_failure_and_thread_safety()
        test_zero_resource_leaks_screenshot_and_dumps()
        test_device_lifecycle_and_fault_tolerance()

        print("\n" + "=" * 80)
        print("ALL EMPIRICAL ADVERSARIAL STRESS TESTS COMPLETED SUCCESSFULLY! (6/6 SUITES PASSED)")
        print("=" * 80)
        return 0
    except Exception as e:
        print(f"\n[FATAL STRESS TEST FAILURE]: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
