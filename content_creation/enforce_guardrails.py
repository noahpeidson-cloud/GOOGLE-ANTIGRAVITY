import ast
import os
import sys

def check_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            tree = ast.parse(f.read(), filename=filepath)
        except SyntaxError as e:
            print(f"Syntax Error in {filepath}: {e}")
            return False

    violations = []

    for node in ast.walk(tree):
        # Enforce R27: Zero-Friction Fallback (No time.sleep for quotas)
        if isinstance(node, ast.ExceptHandler):
            # Check if this except block is likely catching an API quota error
            is_quota_except = False
            if getattr(node, 'type', None):
                if isinstance(node.type, ast.Name):
                    if 'ResourceExhausted' in node.type.id or 'Quota' in node.type.id:
                        is_quota_except = True
                elif isinstance(node.type, ast.Attribute):
                    if 'ResourceExhausted' in node.type.attr or 'Quota' in node.type.attr:
                        is_quota_except = True
            
            if is_quota_except or not getattr(node, 'type', None): # or a bare except just in case, but let's just check if 'time.sleep' is directly inside it
                for sub_node in ast.walk(node):
                    if isinstance(sub_node, ast.Call):
                        if isinstance(sub_node.func, ast.Attribute):
                            if isinstance(sub_node.func.value, ast.Name) and sub_node.func.value.id == "time" and sub_node.func.attr == "sleep":
                                # To avoid false positives on bare excepts, let's just be careful.
                                violations.append((sub_node.lineno, "R27 Violation: time.sleep() inside quota exception block. Do not use sleep() for 429 quotas."))

        # Enforce R16: Absolute Imports (No relative imports in daemons)
        if isinstance(node, ast.ImportFrom):
            if node.level > 0:
                violations.append((node.lineno, f"R16 Violation: Relative import '{node.module}' detected. Agents are forbidden from using relative imports in executable entrypoints."))

        # Enforce R23: Grounded Model Mandate (No hallucinated models)
        if getattr(node, "value", None) and isinstance(node.value, str):
            val = node.value.lower()
            if "gemini-" + "3.7-pro" in val or "gemini-" + "3.5-pro" in val:
                violations.append((node.lineno, f"R23 Violation: Hallucinated model '{node.value}' detected. Google has not released a 3.7 Pro or 3.5 Pro model."))

    if violations:
        print(f"\n--- Violations in {filepath} ---")
        for lineno, msg in violations:
            print(f"Line {lineno}: {msg}")
        return False
    return True

def scan_directory(directory):
    print(f"Scanning {directory} for R16 and R27 violations...")
    failed = False
    count = 0
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                if not check_file(filepath):
                    failed = True
                count += 1
    
    print(f"\nScanned {count} Python files.")
    if failed:
        print("STATIC AUDIT FAILED: Guardrail violations detected.")
        sys.exit(1)
    else:
        print("STATIC AUDIT PASSED: No R16 or R27 violations detected.")
        sys.exit(0)

if __name__ == "__main__":
    scan_directory(os.path.dirname(os.path.abspath(__file__)))
