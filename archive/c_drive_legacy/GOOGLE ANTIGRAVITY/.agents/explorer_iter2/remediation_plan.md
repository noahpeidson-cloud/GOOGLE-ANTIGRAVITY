# Master Remediation Plan: Challenger 1 Hardening Findings

**Document Version**: 2.0.0  
**Author**: Explorer 1 (Iteration 2 — Challenger 1 Remediation)  
**Target Module**: `G:\My Drive\GOOGLE ANTIGRAVITY\content_creation`  
**Execution Target**: Worker Agent (Implementation)  
**Date**: 2026-08-22  

---

## Executive Summary

Challenger 1 conducted an empirical stress-test across the EDM Short-Form Content Creation pipeline (`content_creation/`) via an 85-test suite (`content_creation/tests/test_adversarial_stress.py`). The audit revealed 8 concrete vulnerabilities, edge-case failures, and specification inconsistencies spanning FFmpeg filter syntax, unicode handling, spam regex precision, safe zone geometry, file format acceptance, dynamic range limiting, and Quality Control (QC) assertions.

This document delivers an exact, step-by-step remediation guide for the Worker agent to implement all necessary fixes across `config.py`, `ingest_assets.py`, `ffmpeg_processor.py`, `metadata_tracker.py`, `orchestrator.py`, `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md`, and the unit/stress test suites.

---

## Finding-by-Finding Detailed Technical Remediation

---

### Finding 1: FFmpeg Drawtext Filter Crash on Unescaped Commas & Punctuation
- **Severity**: High
- **Target File**: `content_creation/ffmpeg_processor.py` (`FilterGraphBuilder.build_video_filter`, lines 320–330)
- **Root Cause**:
  In FFmpeg filtergraph syntax, sequential filters are delimited by commas (`,`), while options within a filter are delimited by colons (`:`). Inside `FilterGraphBuilder.build_video_filter()`, track titles and artist names (e.g. `artist="Skrillex, Fred again.."` or `track="Where You Are, Pt. 2"`) contain commas. Line 323 performs `.replace("'", "").replace(":", r"\:")` but does not escape commas or backslashes. When `",".join(filters)` compiles the filtergraph, the unescaped comma inside the text string splits the `drawtext` filter into invalid filter tokens, causing FFmpeg to fail with syntax errors (`No such filter: ' Fred again..'`).
- **Remediation Specification**:
  1. Escape backslashes first (`.replace('\\', r'\\')`).
  2. Strip or escape single quotes (`.replace("'", "")`).
  3. Escape colons (`.replace(':', r'\:')`).
  4. Escape commas with backslashes (`.replace(',', r'\,')`).
- **Exact Code Diff**:
  ```python
  # File: content_creation/ffmpeg_processor.py
  # <<<<<< BEFORE (lines 322-324)
              display_str = " - ".join(overlay_text)
              # Rendered at Y=350 px (well inside the YouTube 180-1450 & TikTok 160-1470 safe box)
              escaped_text = display_str.replace("'", "").replace(":", r"\:")
  # ====== AFTER
              display_str = " - ".join(overlay_text)
              # Rendered at Y=350 px (well inside the YouTube 180-1450 & TikTok 160-1470 safe box)
              # Escape backslashes, single quotes, colons, and commas for FFmpeg filtergraph syntax safety
              escaped_text = (
                  display_str.replace("\\", r"\\")
                  .replace("'", "")
                  .replace(":", r"\:")
                  .replace(",", r"\,")
              )
  # >>>>>>
  ```
- **Side Effects / Interactions**:
  Safe across all strings; ensures that titles with feature artists (`feat.`, `,`, `&`), punctuation, and subtitles are safely rendered on-screen without filtergraph syntax corruption.
- **Verification Assertion**:
  In `test_adversarial_stress.py`, `test_drawtext_filter_comma_escaping`:
  Splitting by regex `(?<!\\),` (unescaped commas) must leave the `drawtext` filter token intact with `\,`.

---

### Finding 2: Unicode Diacritic Normalization & Artist Name Preservation
- **Severity**: Medium
- **Target File**: `content_creation/ingest_assets.py` (`FilenameNormalizer.sanitize_token`, lines 358–367)
- **Root Cause**:
  `FilenameNormalizer.sanitize_token()` executes `words = re.findall(r"[A-Za-z0-9]+", token)`. Because standard ASCII regex classes omit non-ASCII Latin characters, European electronic music artist names with umlauts, acute/grave accents, or strokes lose characters silently:
  - `"Tiësto"` $\to$ `["Ti", "sto"]` $\to$ `"TiSto"` (drops `ë`)
  - `"Kölsch"` $\to$ `["K", "lsch"]` $\to$ `"KLsch"` (drops `ö`)
  - `"Öwnboss"` $\to$ `["Wnboss"]` $\to$ `"Wnboss"` (drops `Ö`)
  - `"MØ"` $\to$ `["M"]` $\to$ `"M"` (drops `Ø`)
  - `"Beyoncé"` $\to$ `["Beyonc"]` $\to$ `"Beyonc"` (drops `é`)
- **Remediation Specification**:
  1. Import Python standard library `unicodedata`.
  2. Implement pre-mapping for non-decomposing Latin ligatures and stroke characters (e.g. `Ø` $\to$ `O`, `ø` $\to$ `o`, `Æ` $\to$ `Ae`, `æ` $\to$ `ae`, `ß` $\to$ `ss`, `Ł` $\to$ `L`, `ł` $\to$ `l`, `Đ` $\to$ `D`, `đ` $\to$ `d`).
  3. Apply `unicodedata.normalize('NFKD', ...)` to separate base characters from combining diacritics, then encode to ASCII with `ignore` and decode to UTF-8.
  4. Tokenize with `re.findall(r"[A-Za-z0-9]+", decomposed)`.
- **Exact Code Diff**:
  ```python
  # File: content_creation/ingest_assets.py
  # <<<<<< BEFORE (lines 12-20, 358-367)
  from datetime import datetime
  import hashlib
  import json
  import os
  from pathlib import Path
  import re
  import shutil
  import subprocess
  import sys
  ...
      @classmethod
      def sanitize_token(cls, token: str, default: str = "Unknown") -> str:
          """Removes spaces and non-alphanumeric characters for clean token syntax."""
          if not token:
              return default
          # Replace spaces with CamelCase or remove them, strip special chars
          words = re.findall(r"[A-Za-z0-9]+", token)
          if not words:
              return default
          return "".join(word.capitalize() for word in words)
  # ====== AFTER
  from datetime import datetime
  import hashlib
  import json
  import os
  from pathlib import Path
  import re
  import shutil
  import subprocess
  import sys
  import unicodedata
  ...
      LATIN_CHAR_MAP = {
          "Ø": "O", "ø": "o", "Æ": "Ae", "æ": "ae",
          "ß": "ss", "Ł": "L", "ł": "l", "Đ": "D", "đ": "d",
      }

      @classmethod
      def sanitize_token(cls, token: str, default: str = "Unknown") -> str:
          """Removes spaces and non-alphanumeric characters for clean token syntax, normalizing unicode diacritics."""
          if not token:
              return default
          cleaned = token
          for src, dst in cls.LATIN_CHAR_MAP.items():
              cleaned = cleaned.replace(src, dst)
          # Decompose remaining unicode diacritics (e.g. ë -> e, ö -> o, é -> e) to ASCII base glyphs
          decomposed = unicodedata.normalize("NFKD", cleaned).encode("ascii", "ignore").decode("utf-8")
          words = re.findall(r"[A-Za-z0-9]+", decomposed)
          if not words:
              return default
          return "".join(word.capitalize() for word in words)
  # >>>>>>
  ```
- **Verification Assertion**:
  `sanitize_token("Tiësto")` $\to$ `"Tiesto"`, `"Kölsch"` $\to$ `"Kolsch"`, `"Öwnboss"` $\to$ `"Ownboss"`, `"MØ"` $\to$ `"Mo"`, `"Beyoncé"` $\to$ `"Beyonce"`.

---

### Finding 3: Spam Regex Delimiter Evasion via Underscores, Hyphens, Dots & Zero-Space
- **Severity**: Medium
- **Target File**: `content_creation/config.py` (`SPAM_BLOCKLIST_PATTERN`, lines 355–361)
- **Root Cause**:
  `SPAM_BLOCKLIST_PATTERN` in `config.py` used `\s*` between words (e.g. `check\s*bio`, `ticket\s*sale`, `free\s*download`, `dm\s*me`). In regex, `\s` only matches whitespace (`[ \t\n\r\f\v]`). Spammers evading automated filters by using underscores (`check_bio`, `ticket_sale`, `buy_tickets`, `dm_me`), hyphens (`check-bio`, `ticket-sale`, `free-download`), dots (`check.bio`), or zero spaces (`checkbio`, `buytickets`, `ticketsale`) evaded detection.
- **Remediation Specification**:
  Broaden inter-word separator classes in multi-word spam phrases to `[\s_\-\.]*` to capture whitespace, underscores, hyphens, dots, and zero-space concatenations.
- **Exact Code Diff**:
  See Finding 4 for consolidated regex pattern diff.

---

### Finding 4: Spam Filter Precision & Word Boundary Collision Prevention
- **Severity**: Medium
- **Target File**: `content_creation/config.py` (`SPAM_BLOCKLIST_PATTERN`, lines 355–361) & `metadata_tracker.py` (`CommentSpamFilter`)
- **Root Cause**:
  Single-word keywords (`scam`, `leak`) and unanchored phrases (`dm me`) lacked word boundary anchors (`\b`). This led to false-positive collisions on innocent community discussion comments:
  - `"We visited Scamander on our Australia tour"` matched `scam` inside `Scamander`.
  - `"Check the cdm media article"` matched `dm me` inside `c[dm me]dia`.
  - Words like `bleak` or `leakage` risk false-positive triggers if unanchored.
- **Remediation Specification**:
  Apply leading and trailing word boundary anchors (`\b`) to all keywords and phrases where appropriate, while allowing `t.me/` to match protocol prefixes.
- **Exact Code Diff (Findings 3 & 4 Consolidated)**:
  ```python
  # File: content_creation/config.py
  # <<<<<< BEFORE (lines 355-361)
  # Canonical 17-keyword blocklist regex pattern
  SPAM_BLOCKLIST_PATTERN = (
      r"(?i)(t\.me\/|whatsapp|crypto|investment|check\s*bio|full\s*set\s*link|"
      r"telegram|drop\s*your\s*track|promo\s*on|dm\s*to\s*promote|click\s*here|"
      r"ticket\s*sale|buy\s*tickets|leak|scam|dm\s*me|free\s*download)"
  )
  # ====== AFTER
  # Canonical 17-keyword blocklist regex pattern with word boundaries and punctuation evasion handling
  SPAM_BLOCKLIST_PATTERN = (
      r"(?i)(t\.me\/|"
      r"\bwhatsapp\b|"
      r"\bcrypto\b|"
      r"\binvestments?\b|"
      r"\bcheck[\s_\-\.]*bio\b|"
      r"\bfull[\s_\-\.]*set[\s_\-\.]*link\b|"
      r"\btelegram\b|"
      r"\bdrop[\s_\-\.]*your[\s_\-\.]*track\b|"
      r"\bpromo[\s_\-\.]*on\b|"
      r"\bdm[\s_\-\.]*to[\s_\-\.]*promote\b|"
      r"\bclick[\s_\-\.]*here\b|"
      r"\bticket[\s_\-\.]*sales?\b|"
      r"\bbuy[\s_\-\.]*tickets?\b|"
      r"\bleaks?\b|"
      r"\bscams?\b|"
      r"\bdm[\s_\-\.]*me\b|"
      r"\bfree[\s_\-\.]*downloads?\b)"
  )
  # >>>>>>
  ```
- **Verification Assertion**:
  - `check_comment("check_bio")` $\to$ `(True, ["check_bio"])`
  - `check_comment("ticket-sale")` $\to$ `(True, ["ticket-sale"])`
  - `check_comment("We visited Scamander on our Australia tour")` $\to$ `(False, [])`
  - `check_comment("Check the cdm media article")` $\to$ `(False, [])`

---

### Finding 5: Safe Zone Coordinate & Bounding Box Geometric Consistency
- **Severity**: Low-Medium
- **Target Files**:
  - `content_creation/config.py` (lines 142–149, 166–173)
  - `content_creation/tests/test_config.py` (lines 48, 57)
  - `content_creation/V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` (Section 2.2)
- **Root Cause**:
  - YouTube Safe Zone in `config.py` specified `height: 1160`, but `top_exclusion_y: 180` and `bottom_exclusion_y: 1450` define a vertical span of $1450 - 180 = 1270\text{ px}$ (a 110 px discrepancy).
  - TikTok Safe Zone specified `height: 1250`, but `top_exclusion_y: 160` and `bottom_exclusion_y: 1470` define a vertical span of $1470 - 160 = 1310\text{ px}$ (a 60 px discrepancy).
- **Remediation Specification**:
  Align `height` in `SafeZoneBox` to equal the exact mathematical span between top and bottom exclusion boundaries ($1270\text{ px}$ for YouTube Shorts, $1310\text{ px}$ for TikTok), ensuring that $H = \text{bottom\_exclusion\_y} - \text{top\_exclusion\_y}$ and $W = \text{right\_exclusion\_x} - \text{left\_clearance\_x}$ are completely consistent across configuration, tests, and documentation.
- **Exact Code Diff**:
  ```python
  # File: content_creation/config.py
  # <<<<<< BEFORE (lines 142-149)
      safe_zone=SafeZoneBox(
          width=900,
          height=1160,
          top_exclusion_y=180,
          bottom_exclusion_y=1450,
          right_exclusion_x=960,
          left_clearance_x=60,
      ),
  # ====== AFTER
      safe_zone=SafeZoneBox(
          width=900,
          height=1270,  # 1450 - 180 px mathematical safe span
          top_exclusion_y=180,
          bottom_exclusion_y=1450,
          right_exclusion_x=960,
          left_clearance_x=60,
      ),
  # >>>>>>

  # <<<<<< BEFORE (lines 166-173)
      safe_zone=SafeZoneBox(
          width=920,
          height=1250,
          top_exclusion_y=160,
          bottom_exclusion_y=1470,
          right_exclusion_x=960,
          left_clearance_x=40,
      ),
  # ====== AFTER
      safe_zone=SafeZoneBox(
          width=920,
          height=1310,  # 1470 - 160 px mathematical safe span
          top_exclusion_y=160,
          bottom_exclusion_y=1470,
          right_exclusion_x=960,
          left_clearance_x=40,
      ),
  # >>>>>>
  ```
  ```python
  # File: content_creation/tests/test_config.py
  # <<<<<< BEFORE (lines 48, 57)
          self.assertEqual(sz.height, 1160)
  ...
          self.assertEqual(sz.height, 1250)
  # ====== AFTER
          self.assertEqual(sz.height, 1270)
  ...
          self.assertEqual(sz.height, 1310)
  # >>>>>>
  ```
  Update `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` Section 2.2 to reflect `900 x 1270 px` for YouTube Shorts and `920 x 1310 px` for TikTok.

---

### Finding 6: Supported File Extension Symmetric Alignment (`.m4v`)
- **Severity**: Low
- **Target File**: `content_creation/ingest_assets.py` (`FilenameNormalizer.CANONICAL_PATTERN`, lines 334–338)
- **Root Cause**:
  `scan_inbox()` explicitly supported `.m4v` files (`supported_exts = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}`), but `FilenameNormalizer.CANONICAL_PATTERN` regex only permitted `mp4|mov|mkv|avi|webm`. When an `.m4v` video was processed, `parse_filename()` returned `None`.
- **Remediation Specification**:
  Add `m4v` to `FilenameNormalizer.CANONICAL_PATTERN`.
- **Exact Code Diff**:
  ```python
  # File: content_creation/ingest_assets.py
  # <<<<<< BEFORE (lines 334-338)
      CANONICAL_PATTERN = re.compile(
          r"^(?P<date>\d{8})_(?P<event>[A-Za-z0-9]+)_(?P<artist>[A-Za-z0-9]+)_"
          r"(?P<track>[A-Za-z0-9\-]+)_V(?P<version>\d+)_(?P<resolution>\d+p|4k)\.(?P<ext>mp4|mov|mkv|avi|webm)$",
          re.IGNORECASE,
      )
  # ====== AFTER
      CANONICAL_PATTERN = re.compile(
          r"^(?P<date>\d{8})_(?P<event>[A-Za-z0-9]+)_(?P<artist>[A-Za-z0-9]+)_"
          r"(?P<track>[A-Za-z0-9\-]+)_V(?P<version>\d+)_(?P<resolution>\d+p|4k)\.(?P<ext>mp4|mov|mkv|avi|webm|m4v)$",
          re.IGNORECASE,
      )
  # >>>>>>
  ```
- **Verification Assertion**:
  `parse_filename("20260822_EDC_Summit_WhereYouAre_V1_1080p.m4v")` successfully returns dictionary with `"ext": "m4v"`.

---

### Finding 7: Insertion of `alimiter` to Master Audio Filter Chain
- **Severity**: Low
- **Target File**: `content_creation/ffmpeg_processor.py` (`FilterGraphBuilder.build_audio_filter`, lines 347–365)
- **Root Cause**:
  `V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md` Section 3.2 (line 503) and Section 3.3 (line 577) specifies appending `alimiter=limit=-1.5dB:attack=5:release=50` to the audio filtergraph to ensure brickwall peak limiting during two-pass normalization. In `ffmpeg_processor.py`, `build_audio_filter()` omitted the `alimiter` filter stage.
- **Remediation Specification**:
  Append `alimiter=limit=-1.5dB:attack=5:release=50` after the `loudnorm` filter stage when `loudnorm_mode == LoudnormMode.TWO_PASS`.
- **Exact Code Diff**:
  ```python
  # File: content_creation/ffmpeg_processor.py
  # <<<<<< BEFORE (lines 347-363)
          # 2. EBU R128 Two-Pass Loudnorm Normalization
          if loudnorm_mode == LoudnormMode.TWO_PASS and loudnorm_stats:
              loudnorm_filter = (
                  f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}:"
                  f"measured_I={loudnorm_stats.input_i:.2f}:"
                  f"measured_LRA={loudnorm_stats.input_lra:.2f}:"
                  f"measured_TP={loudnorm_stats.input_tp:.2f}:"
                  f"measured_thresh={loudnorm_stats.input_thresh:.2f}:"
                  f"offset={loudnorm_stats.target_offset:.2f}:linear=true"
              )
              filters.append(loudnorm_filter)
          elif loudnorm_mode == LoudnormMode.TWO_PASS:
              # Fallback single-pass loudnorm if pass 1 stats are unavailable
              filters.append(
                  f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}"
              )
  # ====== AFTER
          # 2. EBU R128 Two-Pass Loudnorm Normalization & True Peak Brickwall Limiter
          if loudnorm_mode == LoudnormMode.TWO_PASS and loudnorm_stats:
              loudnorm_filter = (
                  f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}:"
                  f"measured_I={loudnorm_stats.input_i:.2f}:"
                  f"measured_LRA={loudnorm_stats.input_lra:.2f}:"
                  f"measured_TP={loudnorm_stats.input_tp:.2f}:"
                  f"measured_thresh={loudnorm_stats.input_thresh:.2f}:"
                  f"offset={loudnorm_stats.target_offset:.2f}:linear=true"
              )
              filters.append(loudnorm_filter)
              filters.append("alimiter=limit=-1.5dB:attack=5:release=50")
          elif loudnorm_mode == LoudnormMode.TWO_PASS:
              # Fallback single-pass loudnorm if pass 1 stats are unavailable
              filters.append(
                  f"loudnorm=I={AUDIO_TARGET_LUFS}:LRA={AUDIO_TARGET_LRA}:TP={AUDIO_TARGET_TRUE_PEAK}"
              )
              filters.append("alimiter=limit=-1.5dB:attack=5:release=50")
  # >>>>>>
  ```
- **Verification Assertion**:
  `build_audio_filter(loudnorm_stats=stats)` produces a filter containing `"alimiter=limit=-1.5dB:attack=5:release=50"`.

---

### Finding 8: QC True Peak Tolerance Alignment with Global Standards
- **Severity**: Low
- **Target File**: `content_creation/orchestrator.py` (`verify_media_file`, lines 177–183)
- **Root Cause**:
  `GEMINI.md` line 29 and V2 Blueprint mandate: *"True Peak does not exceed -1.5 dBTP."* However, `verify_media_file()` in `orchestrator.py` tested `tp_ok = (measured_tp <= AUDIO_CEILING_TRUE_PEAK)` where `AUDIO_CEILING_TRUE_PEAK = -1.0`. This allowed audio with True Peak of `-1.2 dBTP` to pass verification despite violating the `-1.5 dBTP` standard.
- **Remediation Specification**:
  Change `orchestrator.py` line 178 to evaluate `tp_ok = (measured_tp <= AUDIO_TARGET_TRUE_PEAK)`.
- **Exact Code Diff**:
  ```python
  # File: content_creation/orchestrator.py
  # <<<<<< BEFORE (lines 177-182)
              if tp_match:
                  measured_tp = float(tp_match.group(1))
                  tp_ok = (measured_tp <= AUDIO_CEILING_TRUE_PEAK)
                  if not tp_ok:
                      failures.append(
                          f"True peak ({measured_tp:.1f} dBTP) exceeds hard limit of {AUDIO_CEILING_TRUE_PEAK:.1f} dBTP."
                      )
  # ====== AFTER
              if tp_match:
                  measured_tp = float(tp_match.group(1))
                  tp_ok = (measured_tp <= AUDIO_TARGET_TRUE_PEAK)
                  if not tp_ok:
                      failures.append(
                          f"True peak ({measured_tp:.1f} dBTP) exceeds target limit of {AUDIO_TARGET_TRUE_PEAK:.1f} dBTP."
                      )
  # >>>>>>
  ```
- **Verification Assertion**:
  A rendered file with `measured_tp = -1.2` evaluates `tp_ok == False`, while `measured_tp = -1.5` or `-1.6` evaluates `tp_ok == True`.

---

## Stress Test Suite Alignment (`test_adversarial_stress.py`)

When Challenger 1 authored `content_creation/tests/test_adversarial_stress.py`, tests with `_finding` or `_vulnerability` suffixes asserted the broken/discrepant behavior to prove the existence of each issue.

The Worker agent must update these tests to assert the **hardened, remediated behavior**:

1. **`test_drawtext_filter_comma_escaping`**:
   - Split `v_filter` by unescaped commas (e.g. `re.split(r"(?<!\\),", v_filter)`).
   - Assert `v_filter` contains `\,` (e.g. `Where You Are\, Pt. 2`).
   - Assert that the `drawtext` token is not orphaned.
2. **`test_token_sanitization_unicode_preservation`**:
   - Assert `sanitize_token("Tiësto") == "Tiesto"`
   - Assert `sanitize_token("Kölsch") == "Kolsch"`
   - Assert `sanitize_token("Öwnboss") == "Ownboss"`
   - Assert `sanitize_token("MØ") == "Mo"`
   - Assert `sanitize_token("Beyoncé") == "Beyonce"`
3. **`test_underscore_and_hyphen_obfuscation_blocked`**:
   - Assert `check_comment("check_bio")[0] is True`
   - Assert `check_comment("check-bio")[0] is True`
   - Assert `check_comment("ticket_sale")[0] is True`
   - Assert `check_comment("ticket-sale")[0] is True`
   - Assert `check_comment("buy_tickets")[0] is True`
   - Assert `check_comment("buy-tickets")[0] is True`
   - Assert `check_comment("free_download")[0] is True`
   - Assert `check_comment("dm_me")[0] is True`
   - Assert `check_comment("drop_your_track")[0] is True`
   - Assert `check_comment("dm_to_promote")[0] is True`
4. **`test_no_false_positives_on_benign_words`**:
   - Assert `check_comment("We visited Scamander on our Australia tour")[0] is False`
   - Assert `check_comment("Check the cdm media article")[0] is False`
   - Assert `check_comment("The atmosphere was bleak earlier")[0] is False`
5. **`test_safe_zone_dimension_consistency`**:
   - Assert `yt_sz.height == (yt_sz.bottom_exclusion_y - yt_sz.top_exclusion_y) == 1270`
   - Assert `tt_sz.height == (tt_sz.bottom_exclusion_y - tt_sz.top_exclusion_y) == 1310`
6. **`test_m4v_extension_support`**:
   - Assert `parse_filename("20260822_EDC_Summit_WhereYouAre_V1_1080p.m4v") is not None`
   - Assert `parsed["ext"] == "m4v"`
7. **`test_alimiter_in_filtergraph_builder`**:
   - Assert `"alimiter=limit=-1.5dB:attack=5:release=50" in a_filter`
8. **`test_qc_true_peak_enforces_target`**:
   - Assert `AUDIO_TARGET_TRUE_PEAK == -1.5`
   - Assert `is_compliant_with_target` is False for `-1.2` and True for `-1.5` / `-1.6`.

---

## Worker Execution Checklist & Validation Protocol

```
[ ] 1. Apply config.py diffs:
       - Update SAFE_ZONE_YOUTUBE height to 1270.
       - Update SAFE_ZONE_TIKTOK height to 1310.
       - Update SPAM_BLOCKLIST_PATTERN with delimiter class [\s_\-\.]* and \b boundaries.

[ ] 2. Apply ingest_assets.py diffs:
       - Add LATIN_CHAR_MAP and unicodedata.normalize in FilenameNormalizer.sanitize_token.
       - Add 'm4v' to FilenameNormalizer.CANONICAL_PATTERN regex.

[ ] 3. Apply ffmpeg_processor.py diffs:
       - Add backslash (\\) and comma (\,) escaping in FilterGraphBuilder.build_video_filter.
       - Add 'alimiter=limit=-1.5dB:attack=5:release=50' in FilterGraphBuilder.build_audio_filter.

[ ] 4. Apply orchestrator.py diffs:
       - Update verify_media_file to assert measured_tp <= AUDIO_TARGET_TRUE_PEAK (-1.5 dBTP).

[ ] 5. Apply blueprint and test updates:
       - Update V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md safe zone dimensions (900x1270, 920x1310).
       - Update test_config.py (height assertions to 1270 and 1310).
       - Update test_adversarial_stress.py to assert hardened behavior across all 8 tests.

[ ] 6. Run complete test verification:
       cd "G:\My Drive\GOOGLE ANTIGRAVITY\content_creation"
       python -m unittest discover -s tests -v
       Confirm 100% tests pass (85+ tests).
```
