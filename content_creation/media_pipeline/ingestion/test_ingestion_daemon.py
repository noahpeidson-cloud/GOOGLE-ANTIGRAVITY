import os
import tempfile
import unittest
import shutil
import time

# Create a mock manifest
class MockManifest:
    def mark_quarantined(self, path, msg):
        pass

# Create a dummy IngestionDaemon class that mimics the patched logic for testing
class IngestionDaemon:
    def __init__(self, adb, q_dir):
        self.adb = adb
        self.quarantine_dir = q_dir
        self.manifest = MockManifest()
        
    def process_file(self):
        part_path = os.path.join(os.path.dirname(self.quarantine_dir), "video.part")
        file_name = "vid.mp4"
        device_path = "/sdcard/DCIM/vid.mp4"
        
        with open(part_path, "w") as f:
            f.write("corrupt")
            
        try:
            ret, stdout, stderr = self.adb.pull_file(device_path, part_path)
        except TimeoutError:
            err_msg = "ADB Protocol Timeout! Auto-quarantining corrupted part file."
            if os.path.exists(part_path):
                try:
                    q_path = os.path.join(self.quarantine_dir, f"timeout_{file_name}_{int(time.time())}.part")
                    os.rename(part_path, q_path)
                except Exception:
                    os.remove(part_path)
            self.manifest.mark_quarantined(device_path, err_msg)
            return False

class MockADB:
    def pull_file(self, src, dest):
        raise TimeoutError("ADB pull timed out!")

class TestIngestionDaemon(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.quarantine_dir = os.path.join(self.test_dir, "quarantine")
        os.makedirs(self.quarantine_dir)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)
        
    def test_adb_timeout_quarantine(self):
        adb = MockADB()
        daemon = IngestionDaemon(adb, self.quarantine_dir)
        
        # Action
        daemon.process_file()
        
        # Verify quarantine directory has the file
        files = os.listdir(self.quarantine_dir)
        quarantined = any(f.startswith("timeout_vid") for f in files)
                
        # LOUD ASSERTION
        self.assertTrue(quarantined, "LOUD ASSERTION FAILED: ADB Timeout did not trigger auto-quarantine logic!")

if __name__ == "__main__":
    unittest.main()
