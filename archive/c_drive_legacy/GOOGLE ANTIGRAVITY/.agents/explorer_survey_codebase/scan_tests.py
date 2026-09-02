import os
import ast
import re

workspace_root = r"g:\My Drive\GOOGLE ANTIGRAVITY"

test_suites = {}

for root, dirs, files in os.walk(workspace_root):
    if any(x in root for x in [".pytest_cache", "archive", "venv", "__pycache__", "node_modules"]):
        continue
    # Let's inspect test files
    for f in files:
        if (f.startswith("test_") or f.endswith("_test.py") or f.endswith("_tests.py") or "conftest" in f or "stress" in f) and f.endswith(".py"):
            path = os.path.join(root, f)
            rel = os.path.relpath(path, workspace_root)
            with open(path, "r", encoding="utf-8", errors="ignore") as file:
                content = file.read()
                test_funcs = re.findall(r'def (test_[a-zA-Z0-9_]+)', content)
                test_classes = re.findall(r'class (Test[a-zA-Z0-9_]+)', content)
                fixtures = re.findall(r'@pytest\.fixture', content)
                has_mock = "unittest.mock" in content or "mock" in content.lower()
                test_suites[rel] = {
                    "functions_count": len(test_funcs),
                    "classes_count": len(test_classes),
                    "fixtures_count": len(fixtures),
                    "lines": len(content.splitlines()),
                    "has_mock": has_mock,
                    "sample_tests": test_funcs[:5]
                }

print(f"Total test files found: {len(test_suites)}")
for path, info in sorted(test_suites.items()):
    print(f"{path}: {info['functions_count']} tests, {info['classes_count']} classes, {info['fixtures_count']} fixtures, {info['lines']} lines (mock={info['has_mock']})")
