import os
import sys
import re
from pathlib import Path

prod_dir = Path('G:/My Drive/GOOGLE ANTIGRAVITY/content_creation')
py_files = [f for f in prod_dir.glob('*.py') if not f.name.startswith('test_')]

print(f'Auditing {len(py_files)} production Python files for integrity violations...')
suspicious_patterns = [
    (re.compile(r'if\s+.*==.*[\'\"]test[\'\"]', re.I), 'Hardcoded test condition'),
    (re.compile(r'if\s+.*==.*[\'\"]EDC[\'\"]\s*:\s*return', re.I), 'Hardcoded test return'),
    (re.compile(r'def\s+\w+\(.*?\):\s*return\s+(True|False|\"\"|None|0|1)\s*$', re.I), 'Facade function single return'),
    (re.compile(r'unittest\.mock', re.I), 'Unittest mock in production'),
    (re.compile(r'import\s+mock', re.I), 'Mock module in production'),
    (re.compile(r'sys\.modules\[[\'\"]DaVinciResolveScript[\'\"]\]', re.I), 'DaVinciResolveScript injection in production'),
    (re.compile(r'notimplementederror', re.I), 'NotImplementedError placeholder in production'),
]

findings = []
for p in py_files:
    content = p.read_text(encoding='utf-8', errors='ignore')
    lines = content.splitlines()
    for idx, line in enumerate(lines, 1):
        for pattern, desc in suspicious_patterns:
            if pattern.search(line):
                findings.append((p.name, idx, desc, line.strip()))

if findings:
    print('FINDINGS DETECTED:')
    for f in findings:
        print(f'  {f[0]}:{f[1]} [{f[2]}] -> {f[3]}')
else:
    print('CLEAN: Zero suspicious patterns or test shortcuts found in production Python files.')

# Check for pre-populated result artifacts/logs in workspace
log_files = list(prod_dir.glob('*.log')) + list(prod_dir.glob('*result*')) + list(prod_dir.glob('*output*'))
print(f'Log/Result artifact files in content_creation: {len(log_files)}')
for lf in log_files:
    print(f' - {lf.name}')
