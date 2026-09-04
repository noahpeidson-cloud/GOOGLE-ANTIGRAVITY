import unittest
import tempfile
import shutil
from pathlib import Path
import os
import sys

content_dir = Path("G:/My Drive/GOOGLE ANTIGRAVITY/content_creation")
sys.path.insert(0, str(content_dir))
sys.path.insert(0, str(content_dir / "tests"))

import test_remote_trigger

proposed_file = Path("G:/My Drive/GOOGLE ANTIGRAVITY/.agents/explorer_fix_1/proposed_index.html")
manifest_file = content_dir / "static" / "manifest.json"

def patched_setUp(self):
    self.workspace_dir = tempfile.mkdtemp()
    self.workspace = Path(self.workspace_dir)
    workspace_static = self.workspace / "static"
    workspace_static.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(proposed_file), str(workspace_static / "index.html"))
    shutil.copy(str(manifest_file), str(workspace_static / "manifest.json"))
    from remote_trigger import create_app
    from fastapi.testclient import TestClient
    self.app = create_app(workspace_root=self.workspace)
    self.client = TestClient(self.app)

test_remote_trigger.TestRemoteTriggerPWADashboard.setUp = patched_setUp

suite = unittest.TestLoader().loadTestsFromTestCase(test_remote_trigger.TestRemoteTriggerPWADashboard)
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

print(f"\nRemote Trigger PWA Tests: {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
if not result.wasSuccessful():
    sys.exit(1)
