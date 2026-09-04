#!/usr/bin/env python3
"""
run_e2e_tests.py - Master Test Runner for the Media Ingestion & Viral Grading Pipeline.
Executes the comprehensive 4-tier opaque-box test suite:
- Tier 1: Feature-Level Functional Verification (90 tests across 18 features)
- Tier 2: Boundary Value Analysis & Stress Modes (10 tests)
- Tier 3: Pairwise & Cross-Feature Interactions (7 tests)
- Tier 4: Application End-to-End Workflows (5 tests)
Total: 112 test cases.

Provides formatted CLI summary table and strict zero-exit-code semantics.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import pytest


# Ensure safe console encoding on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Color formatting
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class TierResultSummary:
    def __init__(self, name: str, file_path: str):
        self.name = name
        self.file_path = file_path
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.duration_sec = 0.0
        self.exit_code = 0


class StandaloneTestCollector:
    """Pytest plugin to capture exact test results per tier."""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            if report.passed:
                self.passed += 1
            elif report.failed:
                self.failed += 1
                self.errors.append((report.nodeid, str(report.longrepr)))
            elif report.skipped:
                self.skipped += 1
        elif report.when == "setup" and report.failed:
            self.failed += 1
            self.errors.append((report.nodeid, str(report.longrepr)))


def run_tier(tier_name: str, test_file: Path, verbose: bool = False) -> TierResultSummary:
    summary = TierResultSummary(tier_name, str(test_file))
    collector = StandaloneTestCollector()

    start_time = time.time()
    pytest_args = [str(test_file), "-q"]
    if verbose:
        pytest_args.append("-v")

    exit_code = pytest.main(pytest_args, plugins=[collector])
    summary.duration_sec = round(time.time() - start_time, 2)
    summary.passed = collector.passed
    summary.failed = collector.failed
    summary.skipped = collector.skipped
    summary.exit_code = int(exit_code)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Media Pipeline E2E Master Test Runner")
    parser.add_argument("--tier", type=int, choices=[1, 2, 3, 4], help="Run only a specific test tier")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose pytest output")
    args = parser.parse_args()

    tests_dir = Path(__file__).parent.resolve()
    
    tier_definitions = [
        (1, "Tier 1: Feature Functional Tests", tests_dir / "tier1_feature_tests.py"),
        (2, "Tier 2: Boundary & Stress Tests", tests_dir / "tier2_boundary_tests.py"),
        (3, "Tier 3: Pairwise Interaction Tests", tests_dir / "tier3_pairwise_tests.py"),
        (4, "Tier 4: Application E2E Workflows", tests_dir / "tier4_application_tests.py"),
    ]

    if args.tier:
        tier_definitions = [t for t in tier_definitions if t[0] == args.tier]

    print(f"\n{BOLD}{CYAN}{'='*80}{RESET}")
    print(f"{BOLD}{CYAN}   MEDIA INGESTION & VIRAL GRADING PIPELINE - E2E TEST SUITE RUNNER{RESET}")
    print(f"{BOLD}{CYAN}{'='*80}{RESET}\n")

    overall_start = time.time()
    results: List[TierResultSummary] = []
    total_passed = 0
    total_failed = 0
    total_skipped = 0

    for tier_num, name, file_path in tier_definitions:
        print(f"{BOLD}[*] Executing {name}...{RESET}")
        res = run_tier(name, file_path, verbose=args.verbose)
        results.append(res)
        total_passed += res.passed
        total_failed += res.failed
        total_skipped += res.skipped

        status_str = f"{GREEN}PASSED{RESET}" if res.failed == 0 and res.passed > 0 else f"{RED}FAILED{RESET}"
        print(f"    +-- Status: {status_str} ({res.passed} passed, {res.failed} failed, {res.duration_sec}s)\n")

    overall_duration = round(time.time() - overall_start, 2)
    total_cases = total_passed + total_failed + total_skipped

    # Summary Report Table
    print(f"\n{BOLD}{'='*80}{RESET}")
    print(f"{BOLD}{'TEST EXECUTION SUMMARY':^80}{RESET}")
    print(f"{BOLD}{'='*80}{RESET}")
    print(f"{'Tier Name':<42} | {'Cases':<7} | {'Passed':<7} | {'Failed':<7} | {'Time (s)':<8}")
    print(f"{'-'*80}")

    for r in results:
        status_color = GREEN if r.failed == 0 else RED
        print(f"{r.name:<42} | {r.passed + r.failed + r.skipped:<7} | {status_color}{r.passed:<7}{RESET} | {status_color}{r.failed:<7}{RESET} | {r.duration_sec:<8.2f}")

    print(f"{'-'*80}")
    print(f"{'TOTAL':<42} | {total_cases:<7} | {GREEN if total_failed == 0 else RED}{total_passed:<7}{RESET} | {GREEN if total_failed == 0 else RED}{total_failed:<7}{RESET} | {overall_duration:<8.2f}")
    print(f"{BOLD}{'='*80}{RESET}")

    if total_failed == 0 and total_cases > 0:
        pass_rate = 100.0
        print(f"\n{BOLD}{GREEN}[SUCCESS] ALL TESTS PASSED SUCCESSFULLY! ({total_passed}/{total_cases} cases, {pass_rate:.1f}% pass rate){RESET}")
        print(f"{CYAN}Ready for milestone test certification: TEST_READY.md{RESET}\n")
        sys.exit(0)
    else:
        pass_rate = (total_passed / total_cases * 100) if total_cases > 0 else 0.0
        print(f"\n{BOLD}{RED}[FAILURE] TEST SUITE FAILED ({total_failed} failures, {pass_rate:.1f}% pass rate){RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
