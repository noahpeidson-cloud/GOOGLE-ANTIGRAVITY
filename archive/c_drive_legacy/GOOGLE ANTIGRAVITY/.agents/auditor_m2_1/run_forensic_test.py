import os
import sys
import tempfile
import time
import socket
import json
import hashlib
from pathlib import Path

CRON_DIR = Path(r"g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron")
if str(CRON_DIR) not in sys.path:
    sys.path.insert(0, str(CRON_DIR))

import models
import database
import safety_guardrails
import scanner
from detectors import (
    BaseDetector,
    GhostDaemonsDetector,
    ContextRotDetector,
    EcosystemPollutionDetector,
    SecretZeroDetector,
    PromptFatigueDetector,
)

print("=== FORENSIC TEST SUITE STARTING ===\n")

# -------------------------------------------------------------
# 1. Non-Destructive Cryptographic Snapshot Test
# -------------------------------------------------------------
print("--- 1. Testing Non-Destructive Guarantee (Cryptographic Snapshot) ---")
def compute_tree_hashes(dir_path):
    hashes = {}
    for root, _, files in os.walk(dir_path):
        for f in files:
            fp = os.path.join(root, f)
            rel = os.path.relpath(fp, dir_path)
            with open(fp, "rb") as hf:
                hashes[rel] = hashlib.sha256(hf.read()).hexdigest()
    return hashes

with tempfile.TemporaryDirectory() as tmp_dir:
    # Setup dirty workspace
    (Path(tmp_dir) / "GEMINI.md").write_text("# GEMINI Manifest\n" + "\n".join(f"## Rule {i}\nDesc" for i in range(70)), encoding="utf-8")
    (Path(tmp_dir) / "PROJECT.md").write_text("# Project Spec\n" * 50, encoding="utf-8")
    (Path(tmp_dir) / "README.md").write_text("# Readme\n", encoding="utf-8")
    (Path(tmp_dir) / "BRIEFING.md").write_text("# Briefing\n", encoding="utf-8")
    (Path(tmp_dir) / "ORIGINAL_REQUEST.md").write_text("# Original\n", encoding="utf-8")
    (Path(tmp_dir) / ".env").write_text("API_KEY=your_token_here\nSECRET=YOUR_API_KEY_HERE\n", encoding="utf-8")
    (Path(tmp_dir) / "config.json").write_text('{"key": "placeholder_key"}', encoding="utf-8")
    
    stale_plan = Path(tmp_dir) / "old_plan.md"
    stale_plan.write_text("# Stale plan", encoding="utf-8")
    past_time = time.time() - (72 * 3600)
    os.utime(str(stale_plan), (past_time, past_time))
    
    (Path(tmp_dir) / "plugins" / "feature.disabled").mkdir(parents=True)
    (Path(tmp_dir) / "sports_cards").mkdir(parents=True)
    (Path(tmp_dir) / "sports_cards" / "video.mp4").write_bytes(b"fake mp4 bytes")
    (Path(tmp_dir) / "content_creation").mkdir(parents=True)
    (Path(tmp_dir) / "content_creation" / "card_ladder_data.csv").write_text("card_id,price\n1,100", encoding="utf-8")

    # Compute baseline snapshot
    initial_hashes = compute_tree_hashes(tmp_dir)

    # Execute all detectors individually and combined
    health_scanner = scanner.HealthScanner()
    anomalies = health_scanner.scan_workspace(tmp_dir)
    print(f"Total anomalies detected: {len(anomalies)}")
    assert len(anomalies) >= 6, f"Expected >=6 anomalies, got {len(anomalies)}"

    # Compute post-scan snapshot
    post_hashes = compute_tree_hashes(tmp_dir)
    assert initial_hashes == post_hashes, "FILESYSTEM MUTATION DETECTED DURING SCAN!"
    print("PASS: Cryptographic snapshot verified 0 modifications/deletions.")

# -------------------------------------------------------------
# 2. GhostDaemons Real Socket Probing & Resilience
# -------------------------------------------------------------
print("\n--- 2. Testing GhostDaemons Live Socket Probing ---")
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(("127.0.0.1", 0))
srv.listen(1)
ephemeral_port = srv.getsockname()[1]

try:
    gd = GhostDaemonsDetector(monitored_ports=[ephemeral_port, 59998, 59999])
    res = gd.scan(".")
    assert len(res) == 1, f"Expected 1 occupied port anomaly, got {len(res)}"
    assert res[0].raw_details["port"] == ephemeral_port
    assert res[0].severity == models.Severity.CRITICAL
    assert "10048" in res[0].description or "occupied" in res[0].description
    print(f"PASS: Detected live socket on port {ephemeral_port} with WinError 10048 signature.")
finally:
    srv.close()

# Verify port is now clean
res_after = gd.scan(".")
assert len(res_after) == 0, "Port should be free after server socket closure"
print("PASS: Verified port freed after server closure.")

# -------------------------------------------------------------
# 3. ContextRot Strict Whitelisting & Precision Age Thresholds
# -------------------------------------------------------------
print("\n--- 3. Testing ContextRot Whitelist & Threshold Logic ---")
with tempfile.TemporaryDirectory() as tmp_dir:
    now = time.time()
    # 23.5 hours old (should NOT be flagged)
    fresh_plan = Path(tmp_dir) / "almost_stale_plan.md"
    fresh_plan.write_text("# Plan", encoding="utf-8")
    os.utime(str(fresh_plan), (now - 23.5*3600, now - 23.5*3600))
    
    # 24.5 hours old (SHOULD be flagged)
    stale_plan = Path(tmp_dir) / "truly_stale_plan.md"
    stale_plan.write_text("# Plan", encoding="utf-8")
    os.utime(str(stale_plan), (now - 24.5*3600, now - 24.5*3600))
    
    # Whitelisted files > 200h old (must NEVER be flagged)
    for wl in ["PROJECT.md", "GEMINI.md", "README.md", "BRIEFING.md", "ORIGINAL_REQUEST.md"]:
        f = Path(tmp_dir) / wl
        f.write_text("# Whitelisted", encoding="utf-8")
        os.utime(str(f), (now - 200*3600, now - 200*3600))
    
    crd = ContextRotDetector(threshold_hours=24.0)
    anoms = crd.scan(tmp_dir)
    assert len(anoms) == 1, f"Expected exactly 1 anomaly (truly_stale_plan.md), got {len(anoms)}: {[a.target_path for a in anoms]}"
    assert "truly_stale_plan.md" in anoms[0].target_path
    print("PASS: ContextRot threshold boundary & whitelist protection verified.")

# -------------------------------------------------------------
# 4. SecretZero Token Masking Verification
# -------------------------------------------------------------
print("\n--- 4. Testing SecretZero Redaction & Masking ---")
with tempfile.TemporaryDirectory() as tmp_dir:
    env_file = Path(tmp_dir) / ".env.local"
    env_file.write_text("TEST_API_KEY=your_token_here\nSECRET_KEY=YOUR_API_KEY_HERE\nCUSTOM_TOKEN=sk-abcdef123456789012345\n", encoding="utf-8")
    
    szd = SecretZeroDetector()
    sz_anoms = szd.scan(tmp_dir)
    assert len(sz_anoms) == 3, f"Expected 3 secret zero anomalies, got {len(sz_anoms)}"
    for anom in sz_anoms:
        # Verify plaintext secrets are redacted in description and details
        assert "your_token_here" not in anom.description
        assert "YOUR_API_KEY_HERE" not in anom.description
        assert "sk-abcdef123456789012345" not in anom.description
        assert "***" in anom.description
        assert anom.severity == models.Severity.CRITICAL
    print("PASS: SecretZero token redaction/masking verified.")

# -------------------------------------------------------------
# 5. PromptFatigue Rule Bloat & Duplicate Detection
# -------------------------------------------------------------
print("\n--- 5. Testing PromptFatigue Header & Tag Extraction ---")
with tempfile.TemporaryDirectory() as tmp_dir:
    manifest = Path(tmp_dir) / "GEMINI.md"
    manifest_content = """# Antigravity Manifest
## R1. Workflow Distillation
Description 1

## R2. Zero Discretion
Description 2

## R1. Workflow Distillation
Duplicate of R1

<RULE[sports_cards]>
Rule 1
</RULE[sports_cards]>

<RULE[sports_cards]>
Rule 1 duplicate tag
</RULE[sports_cards]>
"""
    manifest.write_text(manifest_content, encoding="utf-8")
    pfd = PromptFatigueDetector(max_lines=5)  # low threshold
    pf_anoms = pfd.scan(tmp_dir)
    assert len(pf_anoms) == 2, f"Expected 2 anomalies (line bloat + duplicates), got {len(pf_anoms)}"
    dup_anom = [a for a in pf_anoms if "Duplicate" in a.description][0]
    assert dup_anom.raw_details["duplicate_count"] >= 1
    print("PASS: PromptFatigue line threshold and duplicate rule detection verified.")

# -------------------------------------------------------------
# 6. AST Guardrail Evasion Attack Matrix
# -------------------------------------------------------------
print("\n--- 6. Testing AST Guardrail Against 15 Evasion Attacks ---")
evasion_attacks = [
    ("os.remove via alias", 'import os as my_os\nmy_os.remove("file.txt")'),
    ("from os import remove alias", 'from os import remove as del_fn\ndel_fn("file.txt")'),
    ("shutil.rmtree alias", 'import shutil as sh\nsh.rmtree("/tmp/foo")'),
    ("pathlib unlink", 'import pathlib\np = pathlib.Path("a.txt")\np.unlink()'),
    ("pathlib rmdir", 'from pathlib import Path\nPath("/tmp").rmdir()'),
    ("os.kill via import", 'import os\nos.kill(1234, 9)'),
    ("subprocess taskkill keyword", 'import subprocess\nsubprocess.run(args=["taskkill", "/F", "/PID", "123"])'),
    ("subprocess pkill list", 'import subprocess\nsubprocess.Popen(["pkill", "-f", "python"])'),
    ("DROP TABLE sql", 'import sqlite3\nconn = sqlite3.connect(":memory:")\nconn.execute("DROP TABLE data;")'),
    ("TRUNCATE sql kw", 'conn.execute(sql="TRUNCATE TABLE users;")'),
    ("eval dynamic", 'eval("__import__(\'os\').remove(\'foo\')")'),
    ("exec dynamic", 'exec("import os; os.system(\'rm -rf /\')")'),
    ("getattr remove", 'import os\nfn = getattr(os, "remove")'),
    ("os.removedirs", 'import os\nos.removedirs("/tmp/dir")'),
    ("os.truncate", 'import os\nos.truncate("file.txt", 0)'),
]

for name, code in evasion_attacks:
    violations = safety_guardrails.scan_code_for_safety(code, filename=name)
    assert len(violations) >= 1, f"Evasion attack NOT detected: {name}\nCode:\n{code}"
print("PASS: All 15 AST evasion attacks caught by SafetyASTVisitor.")

print("\n=== ALL FORENSIC AUDIT EMPIRICAL CHECKS PASSED ===")
