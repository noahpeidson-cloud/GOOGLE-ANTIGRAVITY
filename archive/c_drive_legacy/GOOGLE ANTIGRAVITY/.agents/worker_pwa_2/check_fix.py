# Check and prepare clean index.html content
import re

with open('.agents/explorer_fix_1/proposed_index.html', 'r', encoding='utf-8') as f:
    proposed = f.read()

print('Proposed length:', len(proposed))
print('Proposed contains &times;:', '&times;' in proposed)
print('Proposed contains TRIGGER EDM PIPELINE:', 'TRIGGER EDM PIPELINE' in proposed)
print('Proposed contains [100, 100, 100]:', '[100, 100, 100]' in proposed)
print('Proposed contains [500, 200, 500]:', '[500, 200, 500]' in proposed)
