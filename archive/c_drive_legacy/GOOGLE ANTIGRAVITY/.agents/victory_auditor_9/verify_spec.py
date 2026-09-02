import ast
import json
import re
import sys

spec_path = r"G:\My Drive\GOOGLE ANTIGRAVITY\apps\V1_OMNICHANNEL_ARCHITECTURE_SPEC.md"

with open(spec_path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Loaded spec file: {len(content)} characters, {len(content.splitlines())} lines.")

# 1. Verify Structure & Sections
sections_expected = [
    "1. Executive Summary & Ecosystem Topology",
    "2. End-to-End Orchestration Design",
    "3. Dedicated Chrome Extension & Mobile to GCP Ingestion Transfer Protocol",
    "4. Messaging, Staging & Distributed Processing with Apache Spark on GCP",
    "5. Frontend Architecture, Modern Web Guidance & Performance Engineering",
    "6. Strict Accessibility (a11y) Standards & Compliance",
    "7. Mandatory CI/CD Verification & Testing Gates",
    "8. Implementation & Remediation Roadmap"
]

for sec in sections_expected:
    if sec in content:
        print(f"[PASS] Section found: {sec}")
    else:
        print(f"[FAIL] Missing section: {sec}")

# 2. Extract and syntax-check code blocks
# Python blocks
py_blocks = re.findall(r"```python(.*?)```", content, re.DOTALL)
print(f"\nFound {len(py_blocks)} Python code blocks.")
for i, block in enumerate(py_blocks):
    clean_code = "\n".join([line for line in block.splitlines() if not line.strip().startswith("# filepath:")])
    try:
        ast.parse(clean_code)
        print(f"[PASS] Python code block {i+1} parsed successfully with AST.")
    except SyntaxError as e:
        print(f"[FAIL] Python code block {i+1} syntax error: {e}")

# JSON blocks
json_blocks = re.findall(r"```json(.*?)```", content, re.DOTALL)
print(f"\nFound {len(json_blocks)} JSON code blocks.")
for i, block in enumerate(json_blocks):
    clean_json = block.strip()
    try:
        data = json.loads(clean_json)
        print(f"[PASS] JSON code block {i+1} parsed successfully as valid JSON (keys: {list(data.keys())[:3]}).")
    except json.JSONDecodeError as e:
        print(f"[FAIL] JSON code block {i+1} decode error: {e}")

# Requirement 1: Ecosystem Audit & Synthesis
footprints = ["agy_chrome_extension", "agy_daemon", "agy_mobile"]
print("\nRequirement 1: Ecosystem Footprints Check:")
for fp in footprints:
    if fp in content:
        print(f"[PASS] Footprint '{fp}' present and audited.")
    else:
        print(f"[FAIL] Footprint '{fp}' missing.")

# Requirement 2: Exact Data Transfer Protocol
print("\nRequirement 2: Data Transfer Protocol Check:")
protocol_terms = ["OAuth2", "PKCE", "DomScrapePayload.proto", "/v1/telemetry/dom", "Cloud Armor", "Cloud Run Ingestion", "Pub/Sub"]
for pt in protocol_terms:
    if pt in content:
        print(f"[PASS] Term '{pt}' present in Data Transfer Protocol.")
    else:
        print(f"[FAIL] Term '{pt}' missing.")

# Requirement 3: Apache Spark Integration
print("\nRequirement 3: Apache Spark Integration Check:")
spark_terms = ["Structured Streaming", "RocksDBStateStoreProvider", "BigLake", "Iceberg", "PySpark", "Dataproc Serverless", "Airflow", "Cloud Composer"]
for st in spark_terms:
    if st in content:
        print(f"[PASS] Spark term '{st}' present.")
    else:
        print(f"[FAIL] Spark term '{st}' missing.")

# Requirement 4: Accessibility & Web Performance Testing Gates
print("\nRequirement 4: a11y and Web Performance Gates Check:")
gate_terms = ["WCAG 2.1", "Level AA", "LCP < 2.5", "Largest Contentful Paint", "axe-core", "Pa11y", "Lighthouse CI", "Playwright", "48x48px"]
for gt in gate_terms:
    if gt in content:
        print(f"[PASS] Gate term '{gt}' present.")
    else:
        print(f"[FAIL] Gate term '{gt}' missing.")
