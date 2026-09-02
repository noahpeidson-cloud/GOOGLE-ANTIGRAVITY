import unittest
import tempfile
import shutil
from pathlib import Path
import os
import sys

content_dir = Path("G:/My Drive/GOOGLE ANTIGRAVITY/content_creation")
sys.path.insert(0, str(content_dir))
sys.path.insert(0, str(content_dir / "tests"))

import test_adversarial_pwa_dom

proposed_dir = tempfile.mkdtemp()
proposed_file = Path("G:/My Drive/GOOGLE ANTIGRAVITY/.agents/explorer_fix_1/proposed_index.html")
manifest_file = content_dir / "static" / "manifest.json"

shutil.copy(str(proposed_file), os.path.join(proposed_dir, "index.html"))
shutil.copy(str(manifest_file), os.path.join(proposed_dir, "manifest.json"))

def patched_setUp_dom(self):
    self.static_dir = Path(proposed_dir)
    self.index_path = self.static_dir / "index.html"
    with open(self.index_path, "rb") as f:
        self.raw_bytes = f.read()
    self.html_content = self.raw_bytes.decode("utf-8")
    self.dom = test_adversarial_pwa_dom.DOMElementExtractor()
    self.dom.feed(self.html_content)

def patched_setUp_js(self):
    self.static_dir = Path(proposed_dir)
    self.index_path = self.static_dir / "index.html"
    with open(self.index_path, "rb") as f:
        raw = f.read()
    self.html_content = raw.decode("utf-8")
    import re
    match = re.search(r"<script>([\s\S]*?)</script>", self.html_content)
    self.script_content = match.group(1)

def patched_setUp_css(self):
    self.static_dir = Path(proposed_dir)
    self.index_path = self.static_dir / "index.html"
    with open(self.index_path, "rb") as f:
        raw = f.read()
    self.html_content = raw.decode("utf-8")
    self.dom = test_adversarial_pwa_dom.DOMElementExtractor()
    self.dom.feed(self.html_content)
    self.css_content = self.dom.get_combined_style()

def patched_setUp_manifest(self):
    self.static_dir = Path(proposed_dir)
    self.manifest_path = self.static_dir / "manifest.json"
    import json
    with open(self.manifest_path, "r", encoding="utf-8") as f:
        self.manifest = json.load(f)

def patched_setUp_server(self):
    self.workspace_dir = tempfile.mkdtemp()
    self.workspace = Path(self.workspace_dir)
    workspace_static = self.workspace / "static"
    workspace_static.mkdir(parents=True, exist_ok=True)
    shutil.copy(str(Path(proposed_dir) / "index.html"), str(workspace_static / "index.html"))
    shutil.copy(str(Path(proposed_dir) / "manifest.json"), str(workspace_static / "manifest.json"))
    from remote_trigger import create_app
    from fastapi.testclient import TestClient
    self.app = create_app(workspace_root=self.workspace)
    self.client = TestClient(self.app)

test_adversarial_pwa_dom.TestPWADOMStructure.setUp = patched_setUp_dom
test_adversarial_pwa_dom.TestJavaScriptContractsAndAST.setUp = patched_setUp_js
test_adversarial_pwa_dom.TestPWACSSMobileResponsiveness.setUp = patched_setUp_css
test_adversarial_pwa_dom.TestPWAManifestSchema.setUp = patched_setUp_manifest
test_adversarial_pwa_dom.TestFastAPIServerEndpointsIntegration.setUp = patched_setUp_server

suite = unittest.TestLoader().loadTestsFromModule(test_adversarial_pwa_dom)
runner = unittest.TextTestRunner(verbosity=2)
result = runner.run(suite)

shutil.rmtree(proposed_dir, ignore_errors=True)

print(f"\nFinal Result: {len(result.failures)} failures, {len(result.errors)} errors out of {result.testsRun} tests.")
if not result.wasSuccessful():
    sys.exit(1)
