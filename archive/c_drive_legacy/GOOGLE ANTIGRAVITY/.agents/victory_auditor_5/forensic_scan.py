import os
import glob
import re
import ast

target_dir = r"G:\My Drive\GOOGLE ANTIGRAVITY\content_creation"
prod_files = [
    os.path.join(target_dir, f)
    for f in os.listdir(target_dir)
    if f.endswith(".py") and not f.startswith("test_")
]

print(f"Auditing {len(prod_files)} production Python files:")
for f in prod_files:
    print(f" - {os.path.basename(f)} ({os.path.getsize(f):,} bytes)")

print("\n" + "="*80)
print("PHASE 1: AST ANALYSIS & SUSPICIOUS NODE CHECK")
print("="*80)

for fpath in prod_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as fp:
        source = fp.read()
    
    try:
        tree = ast.parse(source, filename=fname)
    except SyntaxError as e:
        print(f"[SYNTAX ERROR] in {fname}: {e}")
        continue
    
    # Check for empty functions or functions with only Pass/return constant
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            # Check if docstring is the only thing or docstring + pass
            real_stmts = [
                s for s in body 
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))
            ]
            if len(real_stmts) == 0:
                print(f"[EMPTY FUNCTION] {fname}:{node.lineno} -> def {node.name}() has empty body / docstring only")
            elif len(real_stmts) == 1:
                stmt = real_stmts[0]
                if isinstance(stmt, ast.Pass):
                    print(f"[PASS ONLY FUNCTION] {fname}:{node.lineno} -> def {node.name}() contains only 'pass'")
                elif isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                    print(f"[NOT IMPLEMENTED] {fname}:{node.lineno} -> def {node.name}() raises NotImplementedError")

print("\n" + "="*80)
print("PHASE 2: TEXT & REGEX SCAN FOR FACADES / HARDCODED CHEATS")
print("="*80)

patterns = [
    (r"os\.environ\.get\(['\"](MOCK|TEST|CI|STUB)", "Test/Mock environment bypass"),
    (r"if\s+['\"]test['\"]\s+in", "Test string conditional branch"),
    (r"return\s+['\"]fake", "Fake return literal"),
    (r"return\s+['\"]mock", "Mock return literal"),
    (r"return\s+202\b", "Hardcoded HTTP 202 status"),
    (r"return\s+409\b", "Hardcoded HTTP 409 status"),
]

for fpath in prod_files:
    fname = os.path.basename(fpath)
    with open(fpath, "r", encoding="utf-8") as fp:
        lines = fp.readlines()
    for lno, line in enumerate(lines, 1):
        for pat, desc in patterns:
            if re.search(pat, line, re.IGNORECASE):
                print(f"[{desc}] {fname}:{lno} -> {line.strip()}")

print("\n" + "="*80)
print("PHASE 3: PRE-POPULATED RESULT LOGS & ARTIFACT SCAN")
print("="*80)
all_files = glob.glob(r"G:\My Drive\GOOGLE ANTIGRAVITY\content_creation\**\*", recursive=True)
log_artifacts = [f for f in all_files if f.endswith((".log", ".txt", ".json", ".out")) and ".agents" not in f]
print(f"Found {len(log_artifacts)} non-code artifacts in content_creation:")
for art in log_artifacts:
    print(f" - {os.path.relpath(art, target_dir)}")

print("\nForensic scan complete.")
