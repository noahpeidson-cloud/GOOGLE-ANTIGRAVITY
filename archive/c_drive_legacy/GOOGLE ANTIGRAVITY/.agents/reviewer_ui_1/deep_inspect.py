import re

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

print("=== 1. CSS GRID & LAYOUT CHECK ===")
match = re.search(r'grid-template-areas:([^;]+);', html)
if match:
    print("Found grid-template-areas:", match.group(1).strip())

match_rows = re.search(r'grid-template-rows:([^;]+);', html)
if match_rows:
    print("Found grid-template-rows:", match_rows.group(1).strip())

match_cols = re.search(r'grid-template-columns:([^;]+);', html)
if match_cols:
    print("Found grid-template-columns:", match_cols.group(1).strip())

print("\n=== 2. SAFE ZONE HUD CHECK ===")
for m in re.finditer(r'(safe-zone-overlay|hud-overlay|shorts|tiktok)[^>]*', html, re.I):
    print("Matched HUD element:", m.group(0)[:120])

print("\n=== 3. OMNICHANNEL GUARDRAILS CHECK ===")
for term in ['content-id-guardrail-banner', 'clamp-59s-btn', 'ghost-link-badge', '59.00']:
    print(f"Contains '{term}':", term in html)

print("\n=== 4. JAVASCRIPT EVENT LISTENERS & LOGIC CHECK ===")
js_matches = re.findall(r'(addEventListener\([\'\"][^\'\"]+[\'\"]|function\s+[a-zA-Z0-9_]+|class\s+[a-zA-Z0-9_]+)', html)
print(f"Total JS functions/classes/listeners found: {len(js_matches)}")
for m in js_matches[:25]:
    print(" -", m)

print("\n=== 5. CHECK FOR FAKE/HARDCODED TEST OUTPUTS ===")
suspicious = [
    'mock_test_result', 'fake_', 'simulate_success', 'hardcoded', 'TODO: implement', 'FIXME'
]
for s in suspicious:
    count = html.count(s)
    print(f"Contains suspicious token '{s}': {count}")
