# Milestone 2 Detector Suite Investigation & Implementation Blueprints

**Agent**: `explorer_m2_2`  
**Working Directory**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m2_2`  
**Target Module**: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\`  
**Target Detectors**:
1. `detectors/ecosystem_pollution.py`
2. `detectors/secret_zero.py`
3. `detectors/prompt_fatigue.py`

---

## 1. Observation

1. **Architecture & Existing Infrastructure (`.agents/cron/`)**:
   - `models.py` defines `AnomalyRecord` (lines 30-68), `DetectorType` (lines 15-21: `GHOST_DAEMONS`, `CONTEXT_ROT`, `ECOSYSTEM_POLLUTION`, `SECRET_ZERO`, `PROMPT_FATIGUE`), and `Severity` (lines 8-13: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`).
   - `config.py` defines key constants: `PROMPT_FATIGUE_MAX_LINES = 100`, `BLACKLIST_TOKEN_PATTERNS` (lines 24-36), and `WHITELISTED_FILENAMES` (lines 15-21: `PROJECT.md`, `GEMINI.md`, `README.md`, `BRIEFING.md`, `ORIGINAL_REQUEST.md`).
   - `database.py` includes `HISTORICAL_LIFELINES_DATA` (lines 12-63) with exact entries for `ECOSYSTEM_POLLUTION_DISABLED_PLUGINS`, `SECRET_ZERO_PLACEHOLDER_KEYS`, and `PROMPT_FATIGUE_MANIFEST_BLOAT`.
   - `safety_guardrails.py` statically bans destructive functions (`os.remove`, `os.unlink`, `os.rmdir`, `os.kill`, `shutil.rmtree`, `taskkill`, `pkill`, `DROP TABLE`, `TRUNCATE`). All detectors must be 100% read-only.
   - `tests/conftest.py` provides `FileSystemSnapshot` (lines 19-61) verifying 0 file modifications during scans.

2. **Real Workspace Artifacts & Contamination Signatures**:
   - `.disabled` Plugins: Multiple plugin skill directories ending in `.disabled` exist in `.gemini/config/plugins/data-agent-kit-plugin/skills/` (e.g. `bigquery_ai_ml.disabled`, `gcp_spark.disabled`, `dataform_bigquery.disabled`, `gcp_dataflow.disabled`).
   - Isolated Tracks (`GEMINI.md:14-23`):
     - `[TRACK 1] /sports_cards`: Card Ladder ETL, card portfolio, PSA/BGS/SGC slabs, Beckett checklists, trading card models.
     - `[TRACK 2] /content_creation`: FFmpeg media engineering, HDR video, DaVinci Resolve timelines, EDM concert clips, audio DSP.
     - `[TRACK 3] /apps`: Next.js, React, Chrome Extension, PWA mobile trigger.
     - `[TRACK 4] /travel_and_life`: Travel itineraries, flight logistics, Google Maps location scouting.
   - Secret Zero: Workspace `.env` currently contains placeholder token `GITHUB_PERSONAL_ACCESS_TOKEN=your_github_classic_pat_here` on line 2, and real credential strings requiring masking.
   - Prompt Fatigue: `GEMINI.md` manifest currently has 60 lines. Prompt fatigue occurs when line count > 100 or when duplicate rule headings exist.

---

## 2. Logic Chain

1. **Ecosystem Pollution Detection Logic (`detectors/ecosystem_pollution.py`)**:
   - *Observation*: Unused `.disabled` directories confuse workspace crawlers and agents, while cross-track file leakage causes cross-domain contamination and context dilution.
   - *Design*:
     - **Dimension 1 (.disabled Directories)**: Walk `workspace_root` (and plugin directories if present), skipping standard cache folders (`.git`, `__pycache__`, `.pytest_cache`, `node_modules`, `venv`, `.venv`, `.next`, `dist`, `build`). Any directory ending in `.disabled` is flagged with `DetectorType.ECOSYSTEM_POLLUTION` and `Severity.LOW`.
     - **Dimension 2 (Cross-Track Leaks)**: Inspect the 4 isolated track directories (`sports_cards`, `content_creation`, `apps`, `travel_and_life`). If files containing distinctive domain markers of Track A (e.g., `CardLadder`, `card_ladder`, `psa_submission`, `slab_serial` for sports cards) are found inside Track B (e.g., `content_creation`), flag with `DetectorType.ECOSYSTEM_POLLUTION` and `Severity.MEDIUM`. Whitelist standard documentation files (`GEMINI.md`, `PROJECT.md`, `README.md`).

2. **Secret Zero Detection & Value Masking Logic (`detectors/secret_zero.py`)**:
   - *Observation*: Unresolved placeholder tokens (`your_token_here`, `YOUR_API_KEY_HERE`, `TODO_TOKEN`) leave configurations non-functional, while exposing plaintext API keys in logs or telemetry causes credential leakage.
   - *Design*:
     - Target files: `.env`, `.env.*` (e.g. `.env.local`, `.env.test`, `.env.example`), `*.json` (e.g. `config.json`, `credentials.json`, `client_secret.json`), `*.yaml`/`*.yml`, `*.toml`.
     - Patterns: Match tokens against `BLACKLIST_TOKEN_PATTERNS` plus common regexes (`your_token_here`, `YOUR_API_KEY_HERE`, `sk-[a-zA-Z0-9]{20,}`, `AIzaSy[0-9A-Za-z_-]{33}`, `AQ\.[0-9A-Za-z_-]{30,}`, `ghp_[0-9A-Za-z]{36}`, `CHANGE_ME`, `TODO_TOKEN`).
     - **Mandatory Value Masking**: Function `mask_secret(val: str) -> str` returns `val[:6] + "***"` for strings > 6 characters and `"***"` for shorter strings. Real secret tokens are NEVER written in plaintext to `description` or `raw_details`.
     - Severity: `Severity.CRITICAL`.

3. **Prompt Fatigue Detection & Token Estimation Logic (`detectors/prompt_fatigue.py`)**:
   - *Observation*: Hardcoded procedural rules bloating `GEMINI.md` dilute the context window.
   - *Design*:
     - Locate `GEMINI.md` in `workspace_root` (and track sub-manifests if present).
     - Compute exact metrics:
       - `line_count = len(lines)`
       - `word_count = sum(len(line.strip().split()) for line in lines if line.strip())`
       - `estimated_tokens = int(word_count * 1.3)` (as specified: `word count * 1.3`).
     - **Rule Bloat Check**: If `line_count > PROMPT_FATIGUE_MAX_LINES` (100 lines), emit `AnomalyRecord` with `DetectorType.PROMPT_FATIGUE`, `Severity.MEDIUM`, recommending rule offloading to `vectorized-rule-registry`.
     - **Duplicate Headings Check**: Parse markdown headings matching `r"^(?:#{1,6}|>\s*#{1,6})\s+(.+)$"`, normalize titles and rule codes (`R1`, `R2`, etc.), and flag duplicate occurrences with `Severity.MEDIUM`.

---

## 3. Caveats

1. **Read-Only Invariant**: Under no circumstances should any detector attempt to delete `.disabled` directories, remove placeholder tokens from `.env`, or modify `GEMINI.md`. All detectors must strictly emit `AnomalyRecord` objects.
2. **Binary and Cache File Exclusion**: Detectors must ignore binary files, large media files, `node_modules`, `.git`, `.venv`, and `.pytest_cache` to prevent high I/O latency and false positives.
3. **Safe File Reading**: All file operations must use `encoding="utf-8", errors="replace"` and wrap I/O in `try...except OSError` to handle transient file locks on Windows (`WinError 32`).

---

## 4. Conclusion & Implementation Blueprints

### File 1: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\ecosystem_pollution.py`

```python
"""Ecosystem Pollution Detector.

Identifies unused .disabled plugin/skill directories and cross-track domain leaks.
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from config import WHITELISTED_FILENAMES
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity


# Standard directory exclusion list to skip build artifacts and virtualenvs
EXCLUDED_SCAN_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
    ".next",
    "dist",
    "build",
    ".gemini",
}

# Domain signatures for detecting cross-track contamination
TRACK_DOMAIN_SIGNATURES: Dict[str, Dict[str, Any]] = {
    "sports_cards": {
        "keywords": [
            "cardladder",
            "card_ladder",
            "slab_serial",
            "psa_10",
            "bgs_9",
            "sgc_10",
            "beckett",
            "trading_card",
            "portfolio.db",
            "card_extraction",
        ],
        "file_patterns": ["*cardladder*", "*beckett*", "*psa_*", "*slab_*"],
        "forbidden_in": ["content_creation", "apps", "travel_and_life"],
    },
    "content_creation": {
        "keywords": [
            "ffmpeg",
            "davinci",
            "edm_mastermind",
            "audio_dsp",
            "video_pipeline",
            "drop_detection",
            "samsung_ingest",
            "hdr_video",
            "concert_sop",
        ],
        "file_patterns": ["*ffmpeg*", "*davinci*", "*samsung_ingest*"],
        "forbidden_in": ["sports_cards", "travel_and_life"],
    },
    "apps": {
        "keywords": [
            "next.config",
            "chrome_extension",
            "manifest.json",
            "tailwind.config",
        ],
        "file_patterns": ["*manifest.json*", "*next.config*"],
        "forbidden_in": ["sports_cards", "content_creation", "travel_and_life"],
    },
    "travel_and_life": {
        "keywords": [
            "flight_itinerary",
            "hotel_booking",
            "google_maps_scouting",
            "travel_logistics",
            "trip_plan",
        ],
        "file_patterns": ["*flight_itinerary*", "*travel_logistics*"],
        "forbidden_in": ["sports_cards", "content_creation"],
    },
}


class EcosystemPollutionDetector(BaseDetector):
    """Detects .disabled plugin directories and cross-track domain boundary contamination."""

    def __init__(self, excluded_dirs: Optional[Set[str]] = None) -> None:
        self.excluded_dirs = set(excluded_dirs or EXCLUDED_SCAN_DIRS)

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Performs a strictly read-only scan for ecosystem pollution anomalies."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        root_path = Path(workspace_root).resolve()

        # 1. Scan for .disabled directories across workspace
        anomalies.extend(self._scan_disabled_directories(root_path))

        # 2. Scan for cross-track domain leaks
        anomalies.extend(self._scan_cross_track_contamination(root_path))

        return anomalies

    def _scan_disabled_directories(self, root_path: Path) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []

        for dirpath, dirnames, _ in os.walk(root_path):
            # Prune excluded directories in-place
            dirnames[:] = [d for d in dirnames if d not in self.excluded_dirs]

            for d in dirnames:
                if d.endswith(".disabled"):
                    full_dir_path = Path(dirpath) / d
                    try:
                        rel_path = str(full_dir_path.relative_to(root_path)).replace("\\", "/")
                    except ValueError:
                        rel_path = str(full_dir_path).replace("\\", "/")

                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                            target_path=rel_path,
                            severity=Severity.LOW,
                            description=f"Unused .disabled plugin/skill directory detected: '{d}' at '{rel_path}'",
                            raw_details={
                                "pollution_type": "disabled_directory",
                                "directory_name": d,
                                "relative_path": rel_path,
                                "is_disabled": True,
                            },
                            confidence=1.0,
                        )
                    )

        return anomalies

    def _scan_cross_track_contamination(self, root_path: Path) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []

        for host_track in ["sports_cards", "content_creation", "apps", "travel_and_life"]:
            track_dir = root_path / host_track
            if not track_dir.exists() or not track_dir.is_dir():
                continue

            for dirpath, dirnames, filenames in os.walk(track_dir):
                dirnames[:] = [d for d in dirnames if d not in self.excluded_dirs]

                for fname in filenames:
                    if fname in WHITELISTED_FILENAMES:
                        continue

                    file_path = Path(dirpath) / fname
                    try:
                        rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
                    except ValueError:
                        rel_path = str(file_path).replace("\\", "/")

                    # Check against all forbidden foreign domain signatures
                    for foreign_domain, spec in TRACK_DOMAIN_SIGNATURES.items():
                        if foreign_domain == host_track:
                            continue
                        if host_track not in spec["forbidden_in"]:
                            continue

                        # Check filename keywords
                        fname_lower = fname.lower()
                        matched_kw = [kw for kw in spec["keywords"] if kw in fname_lower]

                        # Check content keywords for text files (< 200KB)
                        if not matched_kw and file_path.stat().st_size < 200_000:
                            if fname.endswith((".py", ".json", ".csv", ".yaml", ".yml", ".md", ".txt")):
                                try:
                                    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                                        content = f.read().lower()
                                        matched_kw = [kw for kw in spec["keywords"] if kw in content]
                                except OSError:
                                    pass

                        if matched_kw:
                            anomalies.append(
                                AnomalyRecord(
                                    detector_type=DetectorType.ECOSYSTEM_POLLUTION,
                                    target_path=rel_path,
                                    severity=Severity.MEDIUM,
                                    description=(
                                        f"Cross-track domain contamination: {foreign_domain} artifact "
                                        f"found in '{host_track}' track directory ({rel_path})"
                                    ),
                                    raw_details={
                                        "pollution_type": "cross_track_contamination",
                                        "host_track": host_track,
                                        "foreign_domain": foreign_domain,
                                        "matched_keywords": matched_kw,
                                        "file_path": rel_path,
                                    },
                                    confidence=0.95,
                                )
                            )

        return anomalies
```

---

### File 2: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\secret_zero.py`

```python
"""Secret Zero Detector.

Scans environment and configuration files for unconfigured placeholder tokens
and exposed API keys, enforcing strict value masking to prevent credential leakage.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Pattern, Tuple

from config import BLACKLIST_TOKEN_PATTERNS
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity


TARGET_EXTENSIONS: Set[str] = {
    ".env",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
}

TARGET_EXACT_FILES: Set[str] = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.test",
    ".env.example",
    "config.json",
    "credentials.json",
    "client_secret.json",
    "service_account.json",
}

EXCLUDED_DIRS: Set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "venv",
    ".venv",
    ".next",
    "dist",
    "build",
}

# Compiled regex patterns for placeholder tokens and exposed live credentials
SECRET_REGEX_SPECS: List[Tuple[str, Pattern, bool]] = [
    # (Pattern name, Compiled Regex, is_placeholder)
    ("your_token_here", re.compile(r"your[_-]?token[_-]?here", re.IGNORECASE), True),
    ("your_api_key_here", re.compile(r"your[_-]?api[_-]?key[_-]?here", re.IGNORECASE), True),
    ("your_secret_key_here", re.compile(r"your[_-]?secret[_-]?key[_-]?here", re.IGNORECASE), True),
    ("your_pat_here", re.compile(r"your[_-]?(?:github[_-]?)?pat[_-]?here", re.IGNORECASE), True),
    ("placeholder_key", re.compile(r"placeholder[_-]?key", re.IGNORECASE), True),
    ("insert_api_key", re.compile(r"insert[_-]?api[_-]?key[_-]?here", re.IGNORECASE), True),
    ("change_me", re.compile(r"change[_-]?me", re.IGNORECASE), True),
    ("todo_token", re.compile(r"todo[_-]?token", re.IGNORECASE), True),
    ("dummy_token", re.compile(r"dummy[_-]?(?:token|key|secret)", re.IGNORECASE), True),
    # Exposed Real Keys
    ("google_api_key", re.compile(r"AIzaSy[0-9A-Za-z_-]{33}"), False),
    ("gemini_api_key", re.compile(r"AQ\.[0-9A-Za-z_-]{30,}"), False),
    ("github_pat", re.compile(r"(?:ghp_[0-9A-Za-z]{36}|github_pat_[0-9A-Za-z_]{22,})"), False),
    ("openai_api_key", re.compile(r"sk-[a-zA-Z0-9]{20,}"), False),
    ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}"), False),
]


def mask_secret(value: str) -> str:
    """Masks sensitive secret tokens to prevent credential leakage in logs and telemetry."""
    if not value:
        return "***"
    cleaned = value.strip().strip("'\"")
    if len(cleaned) <= 6:
        return "***"
    return f"{cleaned[:6]}***"


class SecretZeroDetector(BaseDetector):
    """Scans config and environment files for placeholder tokens and unmasked secrets."""

    def __init__(self, custom_patterns: Optional[List[str]] = None) -> None:
        self.patterns = list(SECRET_REGEX_SPECS)
        if custom_patterns:
            for p in custom_patterns:
                try:
                    compiled = re.compile(p, re.IGNORECASE)
                    self.patterns.append(("custom_pattern", compiled, True))
                except re.error:
                    pass

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Performs a strictly read-only scan for secret zero placeholder tokens."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        root_path = Path(workspace_root).resolve()

        for dirpath, dirnames, filenames in os.walk(root_path):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIRS]

            for fname in filenames:
                if self._is_target_file(fname):
                    file_path = Path(dirpath) / fname
                    anomalies.extend(self._scan_file_for_secrets(file_path, root_path))

        return anomalies

    def _is_target_file(self, fname: str) -> bool:
        if fname in TARGET_EXACT_FILES or fname.startswith(".env"):
            return True
        ext = os.path.splitext(fname)[1].lower()
        return ext in TARGET_EXTENSIONS

    def _scan_file_for_secrets(self, file_path: Path, root_path: Path) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []
        try:
            rel_path = str(file_path.relative_to(root_path)).replace("\\", "/")
        except ValueError:
            rel_path = str(file_path).replace("\\", "/")

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            return anomalies

        for line_num, line in enumerate(lines, start=1):
            line_str = line.strip()
            # Skip empty lines or pure comment lines
            if not line_str or line_str.startswith("#"):
                continue

            for pattern_name, regex, is_placeholder in self.patterns:
                match = regex.search(line_str)
                if match:
                    raw_val = match.group(0)
                    masked = mask_secret(raw_val)

                    # Extract key name if KEY=VALUE format
                    key_name = ""
                    if "=" in line_str:
                        key_name = line_str.split("=", 1)[0].strip()

                    desc = (
                        f"Unresolved placeholder token '{pattern_name}' found in {rel_path}:{line_num}"
                        if is_placeholder
                        else f"Exposed secret key detected in {rel_path}:{line_num} ({key_name}={masked})"
                    )

                    anomalies.append(
                        AnomalyRecord(
                            detector_type=DetectorType.SECRET_ZERO,
                            target_path=rel_path,
                            severity=Severity.CRITICAL,
                            description=desc,
                            raw_details={
                                "file": rel_path,
                                "line_number": line_num,
                                "key_name": key_name,
                                "token_pattern": pattern_name,
                                "masked_value": masked,
                                "is_placeholder": is_placeholder,
                            },
                            confidence=1.0,
                        )
                    )
                    # Once matched on this line, avoid duplicate noise on same line
                    break

        return anomalies
```

---

### File 3: `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\detectors\prompt_fatigue.py`

```python
"""Prompt Fatigue Detector.

Analyzes GEMINI.md steering manifests for line count bloat (>100 lines),
token estimation bloat (word_count * 1.3), and duplicate rule headings,
recommending rule offloading to vectorized-rule-registry.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from config import PROMPT_FATIGUE_MAX_LINES, WHITELISTED_FILENAMES
from detectors.base import BaseDetector
from models import AnomalyRecord, DetectorType, Severity


HEADING_REGEX = re.compile(r"^(?:#{1,6}|>\s*#{1,6})\s+(.+)$")
RULE_CODE_REGEX = re.compile(r"\b(R\d+)\b")


class PromptFatigueDetector(BaseDetector):
    """Detects manifest rule bloat and redundant rule definitions in GEMINI.md."""

    def __init__(self, max_lines: int = PROMPT_FATIGUE_MAX_LINES) -> None:
        self.max_lines = max_lines

    def scan(self, workspace_root: str) -> List[AnomalyRecord]:
        """Performs a strictly read-only scan of GEMINI.md manifests for prompt fatigue."""
        anomalies: List[AnomalyRecord] = []
        if not os.path.exists(workspace_root):
            return anomalies

        root_path = Path(workspace_root).resolve()

        # Find all GEMINI.md files (root manifest and any track-specific manifests)
        manifest_paths: List[Path] = []
        root_manifest = root_path / "GEMINI.md"
        if root_manifest.exists():
            manifest_paths.append(root_manifest)

        for track in ["sports_cards", "content_creation", "apps", "travel_and_life"]:
            track_manifest = root_path / track / "GEMINI.md"
            if track_manifest.exists():
                manifest_paths.append(track_manifest)

        for manifest in manifest_paths:
            anomalies.extend(self._analyze_manifest(manifest, root_path))

        return anomalies

    def _analyze_manifest(self, manifest_path: Path, root_path: Path) -> List[AnomalyRecord]:
        anomalies: List[AnomalyRecord] = []
        try:
            rel_path = str(manifest_path.relative_to(root_path)).replace("\\", "/")
        except ValueError:
            rel_path = str(manifest_path).replace("\\", "/")

        try:
            with open(manifest_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            return anomalies

        line_count = len(lines)
        word_count = sum(len(line.strip().split()) for line in lines if line.strip())
        estimated_tokens = int(word_count * 1.3)

        # 1. Check Line Count Threshold Bloat
        if line_count > self.max_lines:
            anomalies.append(
                AnomalyRecord(
                    detector_type=DetectorType.PROMPT_FATIGUE,
                    target_path=rel_path,
                    severity=Severity.MEDIUM,
                    description=(
                        f"Manifest rule bloat: {rel_path} has {line_count} lines "
                        f"(exceeds {self.max_lines} line threshold, ~{estimated_tokens} tokens). "
                        "Recommend offloading procedural rules to vectorized-rule-registry."
                    ),
                    raw_details={
                        "file": rel_path,
                        "line_count": line_count,
                        "max_lines": self.max_lines,
                        "word_count": word_count,
                        "estimated_tokens": estimated_tokens,
                        "recommendation": "Offload procedural rules to vectorized-rule-registry (SQLite FTS5)",
                    },
                    confidence=1.0,
                )
            )

        # 2. Check for Duplicate Rule Headings
        duplicate_anomalies = self._check_duplicate_headings(lines, rel_path)
        anomalies.extend(duplicate_anomalies)

        return anomalies

    def _check_duplicate_headings(self, lines: List[str], rel_path: str) -> List[AnomalyRecord]:
        heading_locations: Dict[str, List[int]] = {}

        for line_num, line in enumerate(lines, start=1):
            line_str = line.strip()
            match = HEADING_REGEX.match(line_str)
            if match:
                raw_heading = match.group(1).strip()
                normalized_heading = raw_heading.lower()

                # Extract rule code if present (e.g., 'R1.', 'R2.')
                rule_match = RULE_CODE_REGEX.search(raw_heading)
                key = rule_match.group(1).upper() if rule_match else normalized_heading

                if key not in heading_locations:
                    heading_locations[key] = []
                heading_locations[key].append(line_num)

        duplicates = {k: v for k, v in heading_locations.items() if len(v) > 1}

        if duplicates:
            duplicate_summary = ", ".join([f"{k} (lines: {v})" for k, v in duplicates.items()])
            return [
                AnomalyRecord(
                    detector_type=DetectorType.PROMPT_FATIGUE,
                    target_path=rel_path,
                    severity=Severity.MEDIUM,
                    description=f"Duplicate rule headings detected in {rel_path}: {duplicate_summary}",
                    raw_details={
                        "file": rel_path,
                        "duplicate_headings": duplicates,
                        "duplicate_count": len(duplicates),
                        "recommendation": "Deduplicate repeated rule definitions and consolidate manifest structure",
                    },
                    confidence=1.0,
                )
            ]

        return []
```

---

## 5. Verification Method

To independently verify these designs after implementation by `worker_m2`:

1. **Execute Detector Unit Test Suite**:
   ```powershell
   python -m pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_detectors.py" -v
   ```
2. **Execute Static AST Safety Verification**:
   ```powershell
   python -m pytest "g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron\tests\test_safety_ast.py" -v
   ```
3. **Verify Read-Only FileSystem Invariant**:
   Execute `FileSystemSnapshot` against mock workspaces before and after scanning to prove 0 files were created, modified, or deleted.

---

### Invalidation Conditions
- If any detector writes or modifies a file, invalidating `accidental-data-loss-prevention`.
- If `secret_zero.py` emits unmasked plaintext secrets in `description` or `raw_details`.
- If `prompt_fatigue.py` fails to estimate tokens via `int(word_count * 1.3)` or miss duplicate headings.
