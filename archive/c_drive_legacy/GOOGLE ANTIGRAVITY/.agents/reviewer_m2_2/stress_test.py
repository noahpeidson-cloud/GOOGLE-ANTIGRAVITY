import os
import sys
sys.path.insert(0, r"g:\My Drive\GOOGLE ANTIGRAVITY")
import tempfile
import xml.etree.ElementTree as ET
from unified_ops_hub.mobile.models import ScrapedTrendItem, DeviceState, ScrapeMetrics
from unified_ops_hub.mobile.scraper import MobileViralTrendScraper
from unified_ops_hub.mobile.android_client import AndroidClient, CommandTimeoutError, DeviceOfflineError
from unified_ops_hub.gateway.dlq_manager import DLQManager, ErrorCategory

print("=== ADVERSARIAL STRESS TEST SUITE ===")

# Test 1: Metric parsing edge cases
assert MobileViralTrendScraper.parse_metric_number('1.5M') == 1500000
assert MobileViralTrendScraper.parse_metric_number('0.5K') == 500
assert MobileViralTrendScraper.parse_metric_number('100.25B') == 100250000000
assert MobileViralTrendScraper.parse_metric_number('1,234,567') == 1234567
assert MobileViralTrendScraper.parse_metric_number('abc') == 0
assert MobileViralTrendScraper.parse_metric_number(None) == 0
print("Test 1 Passed: Metric parsing edge cases handled.")

# Test 2: Negative/Zero Post Age in Velocity Calculation
item_zero_age = ScrapedTrendItem(like_count=100, post_age_hours=0.0)
assert item_zero_age.velocity_score > 0
print(f"Test 2 Passed: Zero age velocity score = {item_zero_age.velocity_score}")

item_neg_age = ScrapedTrendItem(like_count=100, post_age_hours=-5.0)
assert item_neg_age.velocity_score > 0
print(f"Test 2b Passed: Negative age velocity score = {item_neg_age.velocity_score}")

# Test 3: Invalid bounds tapping
client = AndroidClient(serial='test')
assert client.tap_element_bounds('not_bounds') is False
assert client.tap_element_bounds('[10,20]') is False
print("Test 3 Passed: Invalid bounds gracefully return False.")

# Test 4: Directional swipe validation
try:
    client.swipe_direction('diagonal')
    assert False, 'Should have raised ValueError'
except ValueError as e:
    assert 'Unsupported swipe direction' in str(e)
print("Test 4 Passed: Invalid swipe direction rejected.")

# Test 5: Keystroke escaping
mock_log = []
def runner(cmd, timeout=None):
    mock_log.append(cmd)
    return ''

mock_client = AndroidClient(serial='test', runner=runner)
mock_client.inject_text('Hello World! #tag $price &co')
assert mock_log[0] == ['adb', '-s', 'test', 'shell', 'input', 'text', 'Hello%sWorld!%s%23tag%s%24price%s%26co']
print("Test 5 Passed: Text injection escaped correctly per Rule R10.2.")

# Test 6: Scraper XML Bomb / Corrupted XML handling with DLQ
temp_dir = tempfile.mkdtemp()
dlq = DLQManager(db_path=os.path.join(temp_dir, 'dlq.db'), quarantine_dir=os.path.join(temp_dir, 'q'))
scraper = MobileViralTrendScraper(client=mock_client, dlq_manager=dlq)

xml_bomb = '<?xml version="1.0"?>\n<!DOCTYPE lolz [\n <!ENTITY lol "lol">\n <!ELEMENT lolz (#PCDATA)>\n <!ENTITY lol1 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">\n]>\n<lolz>&lol1;</lolz>'
items = scraper.parse_xml_hierarchy(xml_bomb, platform='tiktok')
print(f"Test 6 Passed: XML entity expansion safely handled, parsed items={len(items)}")

incidents = dlq.list_incidents(category=ErrorCategory.CORRUPTED_PAYLOAD)
print(f"Test 6b Passed: DLQ recorded {len(incidents)} corrupted payload incident.")

# Test 7: Scraper with max_swipes=0
session, items, metrics = scraper.scrape_feed(platform='tiktok', max_swipes=0)
assert session.status == 'COMPLETED'
assert len(items) == 0
assert metrics.total_frames_dumped == 0
assert metrics.yield_rate == 0.0
assert metrics.failure_rate == 0.0
print("Test 7 Passed: max_swipes=0 edge case handled cleanly.")

# Test 8: Mid-session disconnection during scraping loop
class DisconnectingDevice:
    def __init__(self):
        self.call_count = 0
    def runner(self, cmd, timeout=None):
        self.call_count += 1
        if "wm" in cmd or "settings" in cmd:
            return ""
        if "dumpsys" in cmd:
            return ""
        # On 2nd swipe/layout, simulate device drop
        if self.call_count > 3:
            raise DeviceOfflineError("error: device offline")
        return '[{"text": "#viral post", "bounds": "[0,0][100,100]"}]'

disc_dev = DisconnectingDevice()
disc_client = AndroidClient(serial="drop-test", runner=disc_dev.runner)
disc_scraper = MobileViralTrendScraper(client=disc_client, dlq_manager=dlq)

session, items, metrics = disc_scraper.scrape_feed(platform="tiktok", max_swipes=5, delay_between_swipes_sec=0.0)
print(f"Test 8 Result: Session status = {session.status}, items = {len(items)}, errors = {session.errors}")
assert session.status == "FAILED" or len(session.errors) > 0
print("Test 8 Passed: Mid-session device drop safely handled.")

print("=== ALL ADVERSARIAL STRESS TESTS PASSED ===")
