import os
import sys

vault = r"d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault"
required_field_patterns = [
    ["name"],
    ["context mapping", "context_mapping"],
    ["strengths"],
    ["weaknesses"],
    ["implementation instructions", "implementation_instructions"]
]

results = {}
for root, dirs, files in os.walk(vault):
    if "__pycache__" in root:
        continue
    for f in files:
        path = os.path.join(root, f)
        rel = os.path.relpath(path, vault)
        with open(path, "r", encoding="utf-8") as fp:
            content = fp.read()
        
        # Check first 120 lines or entire file if smaller
        header = "\n".join(content.splitlines()[:120]).lower()
        missing = []
        for aliases in required_field_patterns:
            if not any(alias in header for alias in aliases):
                missing.append(aliases[0])
        results[rel] = {
            "size": len(content),
            "missing": missing,
            "lines": len(content.splitlines())
        }

all_pass = True
print("=" * 90)
print(f"{'Relative Path':45} | {'Lines':>5} | {'Bytes':>7} | {'Status'}")
print("-" * 90)
for k in sorted(results.keys()):
    v = results[k]
    if v["missing"]:
        status = f"FAIL (missing: {', '.join(v['missing'])})"
        all_pass = False
    else:
        status = "PASS (all 5 parts verified)"
    print(f"{k:45} | {v['lines']:5} | {v['size']:7} | {status}")
print("=" * 90)
print(f"Total files checked: {len(results)}")
print(f"Overall Frontmatter Result: {'ALL PASS' if all_pass else 'FAILURES DETECTED'}")
