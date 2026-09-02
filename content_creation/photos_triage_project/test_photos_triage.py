import os
import shutil
import hashlib
import sqlite3
import tempfile
import unittest
import json
from pathlib import Path

# Placeholder for the function we are going to build
try:
    from photos_triage import process_takeout
except ImportError:
    def process_takeout(takeout_dir, output_dir, db_path):
        pass

def get_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

class TestPhotosTriage(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.takeout_dir = os.path.join(self.test_dir, "Takeout")
        self.output_dir = os.path.join(self.test_dir, "Output")
        self.db_path = os.path.join(self.test_dir, "metadata.db")
        
        # Setup fake Takeout structure
        album_dir = os.path.join(self.takeout_dir, "Google Photos", "EDM_Festival_2026")
        os.makedirs(album_dir)
        
        self.test_img = os.path.join(album_dir, "IMG_1234.jpg")
        with open(self.test_img, "wb") as f:
            f.write(os.urandom(1024 * 1024)) # 1MB random data
            
        self.test_json = os.path.join(album_dir, "IMG_1234.jpg.json")
        with open(self.test_json, "w") as f:
            json.dump({
                "title": "IMG_1234.jpg",
                "photoTakenTime": {"timestamp": "1787700000"}
            }, f)
            
        self.original_hash = get_sha256(self.test_img)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_lossless_copy_and_sqlite(self):
        # Action
        process_takeout(self.takeout_dir, self.output_dir, self.db_path)
        
        # 1. Assert file was copied to the output directory
        expected_output_file = os.path.join(self.output_dir, "EDM_Festival_2026", "IMG_1234.jpg")
        self.assertTrue(os.path.exists(expected_output_file), "LOUD ASSERTION FAILED: Output file was not created!")
        
        # 2. Assert lossless bit-for-bit copy
        new_hash = get_sha256(expected_output_file)
        self.assertEqual(self.original_hash, new_hash, "LOUD ASSERTION FAILED: Copied file hash does not match original! Data loss occurred.")
        
        # 3. Assert SQLite metadata injection
        self.assertTrue(os.path.exists(self.db_path), "LOUD ASSERTION FAILED: SQLite database was not created!")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT album, timestamp FROM media WHERE filename=?", ("IMG_1234.jpg",))
        row = cursor.fetchone()
        self.assertIsNotNone(row, "LOUD ASSERTION FAILED: File metadata not found in database!")
        self.assertEqual(row[0], "EDM_Festival_2026")
        self.assertEqual(row[1], "1787700000")
        conn.close()

if __name__ == "__main__":
    unittest.main()
