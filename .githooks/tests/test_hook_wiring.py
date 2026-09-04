"""Guards that the hooks in .githooks/ are syntactically valid and actually wired.

Run:  python -m pytest .githooks/tests/test_hook_wiring.py -v

A hook with a syntax error is worse than no hook: `git commit` prints a shell
error most agents will read as noise and retry past with --no-verify. These are
cheap checks that a broken hook never ships.
"""

import os
import shutil
import subprocess
import sys

import pytest

HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOKS = ['pre-commit', 'pre-push', 'lint-escape-corruption', 'lint-rule-collisions']


def _find_sh():
    found = shutil.which('sh')
    if found:
        return found
    for candidate in (r'C:\Program Files\Git\usr\bin\sh.exe',
                      r'C:\Program Files (x86)\Git\usr\bin\sh.exe',
                      '/bin/sh'):
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError('no POSIX sh on this machine; the hooks cannot be verified')


SH = _find_sh()


def read(name):
    with open(os.path.join(HOOKS_DIR, name), encoding='utf-8') as fh:
        return fh.read()


@pytest.mark.parametrize('hook', HOOKS)
def test_hook_parses(hook):
    path = os.path.join(HOOKS_DIR, hook)
    assert os.path.exists(path), '%s is missing from .githooks/' % hook

    proc = subprocess.run([SH, '-n', path], capture_output=True, text=True)

    assert proc.returncode == 0, '%s has a shell syntax error:\n%s' % (hook, proc.stderr)


def test_pre_commit_invokes_both_lints():
    body = read('pre-commit')

    assert 'lint-escape-corruption' in body, 'escape lint is not wired into pre-commit'
    assert 'lint-rule-collisions' in body, 'rule-collision lint is not wired into pre-commit'


def test_rule_lint_is_gated_on_rule_carrying_paths():
    """It scans the whole repo, so it must only fire when a rule file is staged."""
    body = read('pre-commit')

    assert 'rules/' in body and 'GEMINI' in body and 'CLAUDE' in body, (
        'the rule-collision gate must cover every file that can carry a rule')


def test_allowlist_entries_are_parseable():
    """Every non-comment line must be a bare rule number, or the lint silently
    treats a typo as 'no entry' and blocks a commit for a recorded collision."""
    path = os.path.join(HOOKS_DIR, 'rule-collisions.allow')
    assert os.path.exists(path), 'the allowlist referenced by the lint is missing'

    entries = []
    with open(path, encoding='utf-8') as fh:
        for lineno, raw in enumerate(fh, start=1):
            entry = raw.split('#', 1)[0].strip()
            if not entry:
                continue
            assert ' ' not in entry, (
                '%s:%d has more than one token before the comment: %r' % (path, lineno, entry))
            assert entry.upper().startswith('R'), (
                '%s:%d is not a rule number: %r' % (path, lineno, entry))
            entries.append(entry.upper())

    assert entries, 'the allowlist has no entries; the four known collisions should be listed'
    assert len(entries) == len(set(entries)), 'duplicate entries in the allowlist: %r' % entries


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
