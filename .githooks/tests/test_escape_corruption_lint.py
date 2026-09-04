"""Deterministic tests for .githooks/lint-escape-corruption.

Run:  python -m pytest .githooks/tests/test_escape_corruption_lint.py -v

Every fixture here is a byte sequence that was actually observed in this
workspace, or the exact non-corrupt shape it must not flag. The dictionary in
that hook is only as good as the cases it has been shown; this file is the
record of which ones it has.

Loud assertions, zero shared state. R16 applies -- absolute imports only.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

HOOKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO = os.path.dirname(HOOKS_DIR)
HOOK = os.path.join(HOOKS_DIR, 'lint-escape-corruption')


def _find_sh():
    """Locate a POSIX sh. Fail loudly rather than skipping (R38: no silent pass)."""
    found = shutil.which('sh')
    if found:
        return found
    for candidate in (r'C:\Program Files\Git\usr\bin\sh.exe',
                      r'C:\Program Files (x86)\Git\usr\bin\sh.exe',
                      '/bin/sh'):
        if os.path.exists(candidate):
            return candidate
    raise RuntimeError('no POSIX sh on this machine; the hook cannot be verified')


SH = _find_sh()


@pytest.fixture()
def sample():
    """Write raw bytes to a .md file and run the hook on it. Returns (code, output).

    Uses mkdtemp rather than pytest's tmp_path: the tmp_path factory maintains a
    'pytest-current' symlink under %TEMP% that this machine denies stat access to,
    and the resulting teardown error masks the actual test results.
    """
    root = tempfile.mkdtemp(prefix='escapelint-')

    def _run(raw, name='sample.md'):
        with open(os.path.join(root, name), 'wb') as fh:
            fh.write(raw)
        proc = subprocess.run([SH, HOOK, name], cwd=root,
                              capture_output=True, text=True)
        return proc.returncode, proc.stdout + proc.stderr

    try:
        yield _run
    finally:
        shutil.rmtree(root, ignore_errors=True)


# --------------------------------------------------------------------------
# Variant A -- the escape survives as a literal control byte
# --------------------------------------------------------------------------

def test_bel_from_backslash_a_is_flagged(sample):
    """The live skill-router defect: '| ' + 0x07 + 'rchitect |'."""
    code, out = sample(b'# Title\n\n| skill | \x07rchitect | /infrastructure |\n')

    assert code == 1, 'a BEL byte is never legitimate in markdown\n' + out
    assert '\\a BEL' in out or 'rchitect' in out, out


def test_backspace_byte_is_flagged(sample):
    code, out = sample(b'# Title\n\nSee `\x08ash for details.\n')

    assert code == 1, 'a 0x08 backspace is an interpreted \\b\n' + out


def test_formfeed_and_vtab_are_flagged(sample):
    code, out = sample(b'# Title\n\nalpha\x0cbeta\x0bgamma\n')

    assert code == 1, '0x0c and 0x0b are interpreted \\f and \\v\n' + out


def test_mid_line_cr_on_a_crlf_file_is_flagged(sample):
    """The 423bad9a regression: grep strips CR in text mode and reports clean."""
    code, out = sample(b'# Title\r\n\r\nExecute \x0dun_command now.\r\n')

    assert code == 1, 'a mid-line CR on a CRLF file must not be missed\n' + out


def test_tab_after_visible_content_is_flagged(sample):
    code, out = sample(b'Our Pytest (\tests/test_x.py) proved it.\n')

    assert code == 1, 'a TAB after visible content is a degraded \\t\n' + out


def test_leading_tab_indentation_is_not_flagged(sample):
    code, out = sample(b'# Title\n\n\tindented code line\n\tsecond line\n')

    assert code == 0, 'leading TAB is legitimate indentation\n' + out


def test_plain_crlf_file_is_not_flagged(sample):
    code, out = sample(b'# Title\r\n\r\nOrdinary Windows line endings.\r\n')

    assert code == 0, 'CRLF is the normal case on this machine\n' + out


# --------------------------------------------------------------------------
# Variant B -- the escape ate a character and left no control byte
# --------------------------------------------------------------------------

@pytest.mark.parametrize('damaged,intended', [
    (b'Run un_command to start.\n', 'run_command'),
    (b'Pytest in ests/test_x.py passed.\n', 'tests/'),
    (b'ame: skill-router\n', 'name:'),
    (b'Call erify_hash on it.\n', 'verify_'),
    (b'Wrote esults.json to disk.\n', 'results.json'),
    (b'Build with sc -b now.\n', 'tsc -b'),
    (b'| skill | rchitect | /infra |\n', 'architect'),
    (b'Read .gents/skills/foo.\n', 'agents/'),
    (b'Invoke enchmark_harness now.\n', 'benchmark_harness'),
    (b'Never stage ode_modules here.\n', 'node_modules'),
])
def test_dictionary_token_is_flagged(sample, damaged, intended):
    code, out = sample(b'# Title\n\n' + damaged)

    assert code == 1, 'dictionary must catch the damaged form of %r\n%s' % (intended, out)
    assert 'truncated' in out, out


def test_mangled_bash_fence_is_flagged(sample):
    """PowerShell turns ```bash into ` + 0x08 + ash; strip the byte and `ash remains."""
    code, out = sample(b'# Title\n\n   `ash\n   git status\n')

    assert code == 1, 'a `ash opener silently kills the code fence\n' + out


def test_lone_backtick_line_is_flagged(sample):
    """The matching closing fence: ``` collapses to a single backtick."""
    code, out = sample(b'# Title\n\n```bash\ngit status\n   `\n')

    assert code == 1, 'a lone backtick is a mangled closing fence\n' + out


def test_intact_tokens_are_not_flagged(sample):
    """The un-damaged forms of every dictionary entry must pass together."""
    clean = (b'# Title\n\n'
             b'Run run_command, check tests/test_x.py, set name: value,\n'
             b'call verify_hash, write results.json, build with tsc -b,\n'
             b'assign the architect, read .agents/skills/, invoke\n'
             b'benchmark_harness, and never stage node_modules.\n\n'
             b'```bash\ngit status\n```\n')

    code, out = sample(clean)

    assert code == 0, 'the dictionary must not fire on correct text\n' + out


def test_architect_inside_a_word_is_not_flagged(sample):
    """\\brchitect\\b must not match the 'rchitect' inside 'architect'."""
    code, out = sample(b'# Title\n\nThe architect owns this. Architects too.\n')

    assert code == 0, 'word-boundary anchoring is what keeps this usable\n' + out


def test_non_markdown_files_are_skipped(sample):
    code, out = sample(b'| \x07rchitect |\n', name='sample.txt')

    assert code == 0, 'the hook only claims .md files\n' + out


# --------------------------------------------------------------------------
# The live tree must be clean
# --------------------------------------------------------------------------

def _live_markdown(*relative_dirs):
    paths = []
    for rel in relative_dirs:
        for dirpath, _dirnames, filenames in os.walk(os.path.join(REPO, rel)):
            for name in filenames:
                if name.endswith('.md'):
                    paths.append(os.path.relpath(os.path.join(dirpath, name), REPO))
    assert paths, 'found no markdown under %s; the walk is wrong' % (relative_dirs,)
    return paths


def test_live_rules_and_skills_are_clean():
    """The authored, in-force markdown must be clean.

    Deliberately narrower than the hook's no-argument default, which walks all of
    .agents/. Two subagent briefings from a finished 2026-08-29 run carry live
    corruption and are owned by another lane:

        .agents/teamwork_preview_reviewer_1/BRIEFING.md      irebase.json, ase_agent.py
        .agents/teamwork_preview_worker_remediation/BRIEFING.md   ail_job()

    They are historical run records, not authored policy, so this test does not
    gate on them. Remove this note once that lane repairs them.
    """
    files = _live_markdown('rules', os.path.join('.agents', 'skills'))
    proc = subprocess.run([SH, HOOK] + files, cwd=REPO, capture_output=True, text=True)

    assert proc.returncode == 0, (
        'rules/ or .agents/skills/ carries escape corruption:\n'
        + proc.stdout + proc.stderr)


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
