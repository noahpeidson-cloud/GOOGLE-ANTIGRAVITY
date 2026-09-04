# Script to apply proposed_index.html to static/index.html and index.html
import shutil
import os

source = '.agents/explorer_fix_1/proposed_index.html'
target_static = 'content_creation/static/index.html'
target_root = 'content_creation/index.html'

with open(source, 'r', encoding='utf-8') as f:
    content = f.read()

# Verify content is valid utf-8 and contains all key markers
assert '&times;' in content
assert 'TRIGGER EDM PIPELINE' in content
assert '[100, 100, 100]' in content
assert '[500, 200, 500]' in content
assert '/trigger-pipeline' in content

# Write to target_static
with open(target_static, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f'Wrote {len(content)} chars to {target_static}')

# Write to target_root
with open(target_root, 'w', encoding='utf-8', newline='\n') as f:
    f.write(content)
print(f'Wrote {len(content)} chars to {target_root}')

# Double check decoding
with open(target_static, 'r', encoding='utf-8') as f:
    _ = f.read()
with open(target_root, 'r', encoding='utf-8') as f:
    _ = f.read()
print('Both files successfully verified as clean UTF-8.')
