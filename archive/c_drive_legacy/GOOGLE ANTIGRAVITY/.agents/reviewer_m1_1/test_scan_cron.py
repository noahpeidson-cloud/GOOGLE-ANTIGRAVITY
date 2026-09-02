import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "cron"))

from safety_guardrails import assert_safe_codebase, scan_file_for_safety

cron_dir = Path(__file__).resolve().parent.parent / "cron"
print("Scanning production files in cron_dir:")
for root, dirs, files in os.walk(cron_dir):
    if "tests" in root or "__pycache__" in root:
        continue
    for f in files:
        if f.endswith(".py"):
            fp = os.path.join(root, f)
            v = scan_file_for_safety(fp)
            print(f"  {f}: {len(v)} violations")
            if v:
                print(f"    {v}")

print("Running assert_safe_codebase...")
try:
    assert_safe_codebase(str(cron_dir), exclude_dirs=["tests", "__pycache__", ".pytest_cache"])
    print("assert_safe_codebase passed cleanly!")
except Exception as e:
    print(f"assert_safe_codebase failed: {e}")
