"""Detect and safely clear orphaned git index.lock files.

Usage:  python .githooks/clear_stale_lock.py [--dry-run] [--max-age-min N]

A lock is removed ONLY when both hold:
  1. its mtime is older than --max-age-min (default 15) minutes, and
  2. no git process (git.exe, gk.exe, gk-alpha.exe) is running on this machine.
A young lock, or any lock while a git process exists, is reported and left alone
(exit 1) -- deleting a lock that a live process holds corrupts the index.

Covers the common repo's index.lock and every linked worktree's index.lock
(.git/worktrees/<name>/index.lock). Resolves the common dir with
`git rev-parse --git-common-dir`, so it works from any worktree.

Exit codes: 0 nothing stale (or removed); 1 a lock exists that must not be removed;
2 not inside a git repository.
"""

import argparse
import os
import subprocess
import sys
import time

GIT_PROCESS_NAMES = ("git.exe", "gk.exe", "gk-alpha.exe")


def common_dir() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        print("clear-stale-lock: not inside a git repository", file=sys.stderr)
        sys.exit(2)
    return os.path.abspath(out)


def lock_paths(gitdir: str) -> list[str]:
    paths = [os.path.join(gitdir, "index.lock")]
    wt_root = os.path.join(gitdir, "worktrees")
    if os.path.isdir(wt_root):
        for name in sorted(os.listdir(wt_root)):
            paths.append(os.path.join(wt_root, name, "index.lock"))
    return [p for p in paths if os.path.exists(p)]


def git_processes() -> list[str]:
    if os.name != "nt":
        return []
    try:
        out = subprocess.run(
            ["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, timeout=15
        ).stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ["<tasklist unavailable: assume a git process is running>"]
    found = []
    for line in out.splitlines():
        name = line.split(",")[0].strip('"').lower()
        if name in GIT_PROCESS_NAMES:
            found.append(line.strip())
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--max-age-min", type=float, default=15.0)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    locks = lock_paths(common_dir())
    if not locks:
        print("clear-stale-lock: no index.lock present")
        return 0

    holders = git_processes()
    now = time.time()
    blocked = False
    for lock in locks:
        age_min = (now - os.path.getmtime(lock)) / 60.0
        if age_min < args.max_age_min:
            print(f"clear-stale-lock: KEEP {lock} (age {age_min:.1f} min < {args.max_age_min:g})")
            blocked = True
            continue
        if holders:
            print(f"clear-stale-lock: KEEP {lock} (age {age_min:.1f} min) -- git process running:")
            for h in holders:
                print(f"    {h}")
            blocked = True
            continue
        if args.dry_run:
            print(f"clear-stale-lock: WOULD REMOVE {lock} (age {age_min:.1f} min, no git process)")
            continue
        os.remove(lock)
        print(f"clear-stale-lock: REMOVED {lock} (age {age_min:.1f} min, no git process)")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
