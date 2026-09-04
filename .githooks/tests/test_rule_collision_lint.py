"""Deterministic tests for .githooks/lint-rule-collisions.

Run:  python -m pytest .githooks/tests/test_rule_collision_lint.py -v

Per R02 the hook is not trusted because it was written carefully; it is trusted
because it was executed against fixtures whose correct verdict is known in
advance. Each case builds a throwaway tree, runs the real hook against it, and
asserts on the exit code and the message.

Loud assertions, zero shared state: every test builds its own tree. R16 applies --
absolute imports only, no package-relative anything.
"""

import os
import shutil
import subprocess
import sys
import tempfile

import pytest

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'lint-rule-collisions')


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


def run_hook(tree):
    """Run the real hook with `tree` as the working directory."""
    proc = subprocess.run([SH, HOOK], cwd=tree, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def write(tree, relpath, text):
    path = os.path.join(tree, relpath.replace('/', os.sep))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='\n') as fh:
        fh.write(text)


@pytest.fixture()
def tree():
    """A bare directory that is NOT a git repo, so the hook falls back to cwd."""
    path = tempfile.mkdtemp(prefix='rulelint-')
    os.makedirs(os.path.join(path, 'rules', 'proposed'))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# --------------------------------------------------------------------------
# Collision detection across files that are in force
# --------------------------------------------------------------------------

def test_two_different_titles_on_one_number_is_blocked(tree):
    write(tree, 'rules/03_x.md', '## R39. Git Ownership & Branch Discipline\nbody\n')
    write(tree, 'GEMINI.md', '### R39. The Terminal Confidence Block Guardrail\nbody\n')

    code, out = run_hook(tree)

    assert code == 1, 'unrelated mandates sharing R39 must block; got exit 0\n' + out
    assert 'R39 is claimed by two different rules' in out, out
    assert 'rules/03_x.md' in out and 'GEMINI.md' in out, out


def test_identical_restatement_is_not_a_collision(tree):
    write(tree, 'rules/01_x.md', '## R16. Executable Python Import Guardrail\nbody\n')
    write(tree, 'GEMINI.md', '### R16. Executable Python Import Guardrail\nbody\n')

    code, out = run_hook(tree)

    assert code == 0, 'the same rule restated in two files is duplication, not collision\n' + out


def test_leading_the_and_trailing_parenthetical_still_count_as_one_rule(tree):
    """R36 in the live repo: one file adds 'The ', the other adds '(MS Store CLI)'."""
    write(tree, 'rules/02_x.md', '## R36. GCP Authentication Guardrail\nbody\n')
    write(tree, 'GEMINI.md', '### R36. The GCP Authentication Guardrail (MS Store CLI)\nbody\n')

    code, out = run_hook(tree)

    assert code == 0, 'prefix-equal titles must pass or every commit blocks\n' + out


def test_r2_and_r02_normalize_to_the_same_number(tree):
    write(tree, 'rules/03_x.md', '## R02. Zero-Discretion Empirical Verification\nbody\n')
    write(tree, 'GEMINI.md', '### R2. The Zero-Discretion Mandate (The Leash Protocol)\nbody\n')

    code, out = run_hook(tree)

    assert code == 1, 'R2 and R02 are one number; padding must not hide a conflict\n' + out
    assert 'R2 is claimed by two different rules' in out, out


def test_allowlist_suppresses_a_recorded_collision(tree):
    write(tree, 'rules/03_x.md', '## R39. Git Ownership & Branch Discipline\nbody\n')
    write(tree, 'GEMINI.md', '### R39. The Terminal Confidence Block Guardrail\nbody\n')
    write(tree, '.githooks/rule-collisions.allow', '# recorded debt\nR39  # known conflict\n')

    code, out = run_hook(tree)

    assert code == 0, 'a collision listed in the allowlist must not block\n' + out


def test_allowlist_does_not_suppress_an_unlisted_collision(tree):
    write(tree, 'rules/03_x.md', '## R38. Lane Architecture\n\n## R39. Git Ownership\n')
    write(tree, 'GEMINI.md', '### R38. Fail-Fast API Guardrail\n\n### R39. Confidence Block\n')
    write(tree, '.githooks/rule-collisions.allow', 'R38\n')

    code, out = run_hook(tree)

    assert code == 1, 'R39 is not allowlisted and must still block\n' + out
    assert 'R39 is claimed' in out, out
    assert 'R38 is claimed' not in out, 'R38 was allowlisted and must be silent\n' + out


def test_prefixed_families_do_not_collide_with_plain_numbers(tree):
    """R-APV-01 and R1 are different namespaces and must not be conflated."""
    write(tree, 'rules/04_x.md', '## R-APV-01. Zero-Copy Media Staging Mandate\nbody\n')
    write(tree, 'GEMINI.md', '### R1. Workflow Distillation Directive\nbody\n')

    code, out = run_hook(tree)

    assert code == 0, 'R-APV-01 must not be read as R1\n' + out


# --------------------------------------------------------------------------
# rules/proposed/ number claims
# --------------------------------------------------------------------------

def test_new_proposal_squatting_a_taken_number_is_blocked(tree):
    write(tree, 'rules/03_x.md', '## R48. Claude Code CLI Boundary Traversal\nbody\n')
    write(tree, 'rules/proposed/R48_something.md',
          '---\nproposal: R48\ntype: new\nstatus: proposed\n---\n\n## R48. Something Else\n')

    code, out = run_hook(tree)

    assert code == 1, 'proposing a number already in force must block\n' + out
    assert 'already in force' in out, out


def test_new_proposal_on_a_free_number_passes(tree):
    write(tree, 'rules/03_x.md', '## R48. Claude Code CLI Boundary Traversal\nbody\n')
    write(tree, 'rules/proposed/R49_amendment_protocol.md',
          '---\nproposal: R49\ntype: new\nstatus: proposed\n---\n\n## R49. Protocol\n')

    code, out = run_hook(tree)

    assert code == 0, 'R49 is free and must be allowed\n' + out


def test_amendment_targeting_a_nonexistent_rule_is_blocked(tree):
    write(tree, 'rules/03_x.md', '## R48. Claude Code CLI Boundary Traversal\nbody\n')
    write(tree, 'rules/proposed/R77_ghost.md',
          '---\namends: R77\ntype: amendment\nstatus: proposed\n---\n\nbody\n')

    code, out = run_hook(tree)

    assert code == 1, 'amending a rule that does not exist must block\n' + out
    assert 'no rule R77 exists' in out, out


def test_amendment_targeting_a_live_rule_passes(tree):
    write(tree, 'rules/03_x.md', '## R40. Split-Brain Workspace Isolation\nbody\n')
    write(tree, 'rules/proposed/R40_durability_amendment.md',
          '---\namends: R40\ntype: amendment\nstatus: proposed\n---\n\nbody\n')

    code, out = run_hook(tree)

    assert code == 0, 'a valid amendment must not be treated as a squat\n' + out


def test_two_proposals_claiming_one_number_is_blocked(tree):
    write(tree, 'rules/proposed/R49_first.md',
          '---\nproposal: R49\ntype: new\nstatus: proposed\n---\n\nbody\n')
    write(tree, 'rules/proposed/R49_second.md',
          '---\nproposal: R49\ntype: new\nstatus: proposed\n---\n\nbody\n')

    code, out = run_hook(tree)

    assert code == 1, 'two agents racing for R49 must block\n' + out
    assert 'both propose R49' in out, out


def test_filename_disagreeing_with_frontmatter_is_blocked(tree):
    write(tree, 'rules/proposed/R50_mislabeled.md',
          '---\nproposal: R49\ntype: new\nstatus: proposed\n---\n\nbody\n')

    code, out = run_hook(tree)

    assert code == 1, 'filename R50 vs frontmatter R49 must block\n' + out
    assert 'filename says R50' in out, out


def test_proposal_without_frontmatter_is_blocked(tree):
    write(tree, 'rules/proposed/R51_bare.md', '## R51. No Frontmatter Here\nbody\n')

    code, out = run_hook(tree)

    assert code == 1, 'an undeclared proposal number cannot be checked and must block\n' + out
    assert 'type: new' in out, out


def test_proposed_readme_is_exempt(tree):
    write(tree, 'rules/proposed/README.md', '# Proposed Rules\n\nNo frontmatter, by design.\n')

    code, out = run_hook(tree)

    assert code == 0, 'README.md is documentation, not a proposal\n' + out


# --------------------------------------------------------------------------
# The live repository must be clean, or the hook is unlandable
# --------------------------------------------------------------------------

def test_live_repository_passes(tree):
    repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    proc = subprocess.run([SH, HOOK], cwd=repo, capture_output=True, text=True)

    assert proc.returncode == 0, (
        'the live repo must pass or every rules commit is blocked:\n'
        + proc.stdout + proc.stderr)


if __name__ == '__main__':
    sys.exit(pytest.main([__file__, '-v']))
