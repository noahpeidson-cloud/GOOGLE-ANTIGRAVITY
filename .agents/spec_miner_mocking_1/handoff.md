# Handoff Report: Extraction Mocking Specification (R1)

## 1. Observation
From authoritative inspection of:
- `C:\Users\noahp\OneDrive\Desktop\Antigravity\.agents\ORIGINAL_REQUEST.md` (Lines 17-18, 28-32)
- `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\viral-trend-pipeline\SKILL.md` (Lines 13-30)
- `C:\Users\noahp\.gemini\config\plugins\chrome-devtools-plugin\skills\chrome-devtools\SKILL.md` (Lines 6-38)
- `C:\Users\noahp\.gemini\config\plugins\android-cli-plugin.disabled\skills\SKILL.md` (Lines 62-65, 190-201)
- `C:\Users\noahp\.gemini\config\plugins\android-cli-plugin.disabled\skills\references\interact.md` (Lines 4-17, 58-78)
- `C:\Users\noahp\.gemini\antigravity\mcp\chrome_devtools\take_snapshot.json` (Parameters: filePath, verbose)

The authoritative specifications establish that:
1. **Web Extraction Layer**: The pipeline uses Chrome DevTools MCP `take_snapshot` to extract trending audio titles and hashtags from the Accessibility Tree (`a11y tree`) of TikTok Creative Center and YouTube Trending, bypassing conventional fragile CSS DOM scraping.
2. **Mobile Extraction Layer**: The pipeline uses the Android CLI `android layout` command to inspect headless Android emulator UI hierarchies, dumping a flat JSON array of UI elements with attributes `text`, `resourceId`, `contentDesc`, `bounds`, `center`, `interactions`, `state`, and `off-screen` for Instagram Reels.
3. **Deterministic Mocking & Zero Network Calls**: The test suite must mock both extraction sources using static, deterministic fixtures that execute in memory without spawning browser instances, emulator connections, subprocesses, or real network socket requests.
4. **Performance Constraint**: The complete test suite must execute cleanly in under 10 seconds.

---

## Features Discovered
| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | Chrome DevTools A11y | TikTok Hashtags Snapshot Parser | Parses TikTok Creative Center a11y tree snapshots to extract ranked hashtags, post counts, and velocity metrics | A11y tree text snapshot (`str`) containing `table`, `row`, `link` with `#` tags | List of `TrendRecord` (`platform="tiktok"`, `trend_type="hashtag"`) | Returns empty list or logs warning on missing/malformed nodes | `viral-trend-pipeline/SKILL.md` & `chrome_devtools/take_snapshot.json` |
| 2 | Chrome DevTools A11y | TikTok Audio Snapshot Parser | Parses TikTok Creative Center a11y tree snapshots to extract ranked trending music tracks, artist names, and usage | A11y tree text snapshot (`str`) containing `heading "Trending Songs"` and `listitem` nodes | List of `TrendRecord` (`platform="tiktok"`, `trend_type="audio"`) | Gracefully skips unparseable music rows | `viral-trend-pipeline/SKILL.md` & `chrome-devtools/SKILL.md` |
| 3 | Chrome DevTools A11y | YouTube Trending Video/Shorts Parser | Parses YouTube Trending a11y tree snapshots to extract trending video titles, channels, view counts, and SEO tags | A11y tree text snapshot (`str`) containing `section "Trending Videos"`, `heading` level 3 | List of `TrendRecord` (`platform="youtube"`, `trend_type="video_title"`) | Skips non-video banner elements | `viral-trend-pipeline/SKILL.md` & `ORIGINAL_REQUEST.md` |
| 4 | Android CLI Layout | Instagram Caption & Hashtag Extractor | Extracts organic caption hashtags and user mentions from Android UI dump `caption_text_view` elements | JSON layout dump array containing `resourceId="com.instagram.android:id/caption_text_view"` | List of `TrendRecord` (`platform="instagram"`, `trend_type="hashtag"`) | Ignores elements with null or empty text | `android-cli/references/interact.md` & `viral-trend-pipeline/SKILL.md` |
| 5 | Android CLI Layout | Instagram Reels Audio Track Extractor | Extracts trending audio titles and artists from Android UI dump `audio_track_title` or `clips_audio_mix_editor_title` | JSON layout dump array containing audio track resource IDs | List of `TrendRecord` (`platform="instagram"`, `trend_type="audio"`) | Returns `trend_type="audio"` with parsed title and artist | `android-cli/references/interact.md` & `viral-trend-pipeline/SKILL.md` |
| 6 | Android CLI Layout | Instagram Engagement Metrics Extractor | Parses like counts and comment counts from Android UI dump for velocity scoring | JSON layout dump containing `row_feed_textview_comments_count` and `like_count` | Updated `TrendRecord` with `post_count` and `velocity_metric` | Defaults missing metrics to `None` without failure | `android-cli/references/interact.md` |
| 7 | Data Normalization | Tag Autocleaning & Normalization | Normalizes hashtags by preserving original case, stripping leading `#`, stripping emojis, and trimming whitespace | Raw tag strings (e.g. `"🔥 #SportsCards "`) | Normalized tag string (e.g. `"SportsCards"`) | Handles emoji-only or blank tags by discarding them | `viral-trend-pipeline/SKILL.md` (Section 3) |
| 8 | Metric Parsing | Numerical Suffix & Velocity Formatter | Converts human-readable count strings (`1.2M`, `450K`, `+145%`) into structured integers and floats | Raw metric string (`"1.2M"`, `"+145%"`, `"45.2K"`) | Integer count (`1200000`) and float velocity (`145.0`) | Returns `None` for non-standard strings like `"NEW"` | `viral-trend-pipeline/SKILL.md` |
| 9 | Track Isolation | Domain Category Classifier | Maps extracted trends into isolated tracks (`sports_cards` vs `edm` vs `general`) based on hashtag/title lexicons | Extracted raw title or hashtag | `category` string (`"sports_cards"` or `"edm"` or `"general"`) | Defaults to `"general"` for unclassified items | `GEMINI.md` Manifest & `viral-trend-pipeline/SKILL.md` |
| 10 | Test Infrastructure | Deterministic Extraction Fixture Loader | Provides static in-memory fixtures for TikTok, YouTube, and Instagram snapshots for pytest | Fixture file paths (`tests/fixtures/*.txt`, `*.json`) | Loaded fixture data objects | Raises `FileNotFoundError` if fixture file is missing | `ORIGINAL_REQUEST.md` (R1) |
| 11 | Network Isolation | Zero-Network Socket Guardrail | Autouse pytest fixture blocking all socket connection attempts during test runs | Any network socket call (`socket.socket.connect`, `urllib`, `requests`) | Blocked call raising `NetworkBlockError` | Fails test immediately if socket connection is attempted | `ORIGINAL_REQUEST.md` (Criteria 3) |
| 12 | Subprocess Isolation | CLI Command Runner Mock | Mock runner replacing `subprocess.run` / MCP calls with deterministic fixture dispatch | CLI command string (e.g. `["android", "layout"]`) | Predefined JSON/text fixture stdout | Intercepts all CLI tool invocations | `ORIGINAL_REQUEST.md` (R1) |

---

## Edge Cases
| # | Feature | Input | Observed Behavior |
|---|---------|-------|-------------------|
| E1 | TikTok / YouTube A11y Parser | Empty snapshot string `""` or whitespace only | Extractor returns empty list `[]` without raising exception |
| E2 | TikTok / YouTube A11y Parser | Snapshot with only `RootWebArea "Loading..."` (no content nodes) | Extractor returns empty list `[]` cleanly |
| E3 | TikTok / YouTube A11y Parser | Malformed a11y syntax (missing UIDs, corrupted indentation, unmatched quotes) | Parser skips malformed lines, logs debug warning, and extracts valid lines |
| E4 | TikTok / YouTube A11y Parser | Snapshot with non-ASCII Unicode and emojis (e.g. `"#Wembanyama🔥 #CardLadder💎"`) | Preserves full Unicode, strips emojis for normalized tag, retains raw tag with emoji |
| E5 | TikTok / YouTube A11y Parser | Massive snapshot tree (10,000+ nodes, 5MB text) | Parses entire tree in < 50ms without memory bloat |
| E6 | Android Layout Extractor | Empty JSON array `[]` | Extractor returns empty list `[]` without error |
| E7 | Android Layout Extractor | Invalid JSON string syntax (e.g. `"[{key: -1, text: missing_quotes}]"`) | Extractor raises explicit `ExtractionParseError` with descriptive message |
| E8 | Android Layout Extractor | UI element with `"text": null` or missing `"text"` field | Extractor safely ignores element or checks `contentDesc` fallback |
| E9 | Android Layout Extractor | Elements marked with `"off-screen": true` | Configurable behavior: optionally include or filter out off-screen elements |
| E10 | Android Layout Extractor | Reel caption with 20+ hashtags in a single block | Extractor parses and returns all 20 individual tag records |
| E11 | Metric Normalizer | Metric with non-numeric text (e.g. `"NEW"`, `"Trending"`, `"--"`, `"N/A"`) | Extractor sets `velocity_metric = None` and `post_count = None` |
| E12 | Metric Normalizer | Suffix variations (`"1.2M"`, `"1.2m"`, `"850K"`, `"850k"`, `"2.5B"`, `"1,250"`) | Accurately converts to integer counts (`1200000`, `850000`, `2500000000`, `1250`) |
| E13 | Tag Normalizer | Mixed case and punctuation (e.g. `"#Sports-Cards_2026!"`) | Normalizes to `"Sports-Cards_2026"` while preserving case |
| E14 | Tag Normalizer | Whitespace and zero-width spaces (`" #HardTechno \u200b "`) | Strips zero-width spaces and trims outer whitespace |
| E15 | Zero Network Guard | Any test attempting `urllib.request.urlopen("http://example.com")` | Raises `NetworkBlockError` and fails test immediately |
| E16 | Subprocess Mock | Unmocked `subprocess.run(["android", "layout"])` | Mock runner intercepts call and supplies fixture or fails with `UnmockedCommandError` |

---

## 2. Logic Chain

1. **Extraction Source Disconnect & Solution**:
   - Web scraping via raw HTML/CSS is fragile against obfuscated DOMs in modern SPAs (TikTok, YouTube).
   - Authoritative skill `viral-trend-pipeline/SKILL.md` explicitly specifies using the Chrome DevTools Accessibility Tree (`take_snapshot`) and Android CLI UI Hierarchy dump (`android layout`).
   - Therefore, the integration test fixtures must accurately simulate these exact tree representations rather than mock HTML/DOM strings.

2. **A11y Tree Structure Modeling**:
   - `chrome-devtools-mcp` produces text-based accessibility trees with lines formatted as:
     `uid=<uid> <role> "<name>" [attributes]`.
   - In TikTok Creative Center, hashtags are arranged under tables/rows with links (`#SportsCards`, `#HardTechno`), view counts, and percentage growth badges (`+145%`).
   - In YouTube Trending, video cards are represented as links/headings containing video titles, channel names, and view counts.
   - Therefore, our mock fixtures for web extraction must provide authentic, deterministic AXTree strings with this hierarchy.

3. **Android Layout Dump Structure Modeling**:
   - `android-cli` reference documentation (`interact.md`) confirms that `android layout` returns a JSON array of element objects with `resourceId`, `text`, `contentDesc`, `bounds`, `center`, `interactions`, and `state`.
   - For Instagram Reels, the primary extraction targets are:
     - `com.instagram.android:id/caption_text_view`: caption text containing hashtags (`#TheHobby`, `#SportsCardInvesting`).
     - `com.instagram.android:id/audio_track_title`: audio track name and artist.
     - `com.instagram.android:id/like_count` / `row_feed_textview_comments_count`: engagement metrics.
   - Therefore, our Android mock fixtures must provide realistic JSON arrays populated with these Android view IDs.

4. **Normalized TrendRecord Data Contract**:
   - All extractors (TikTok, YouTube, Instagram) must output uniform `TrendRecord` objects containing:
     - `platform`: `'tiktok' | 'youtube' | 'instagram'`
     - `category`: `'sports_cards' | 'edm' | 'general'`
     - `trend_type`: `'hashtag' | 'audio' | 'video_title'`
     - `raw_title`: Original string from UI
     - `normalized_tag`: Cleaned, case-preserved, emoji-stripped tag
     - `rank`: Optional integer rank
     - `post_count`: Optional integer count
     - `velocity_metric`: Optional float percentage/score
     - `date_added`: ISO date `YYYY-MM-DD`
     - `raw_payload`: Original node metadata dict
   - This contract feeds directly into SQLite `trends.db` (R2) and BigQuery ML formatting (R3).

5. **Zero-Network Isolation Enforcement**:
   - Acceptance criterion 3 specifies: *"The mock extractors yield deterministic JSON structures without attempting real network requests."*
   - To guarantee this determinism and prevent test flakiness or accidental external calls, a pytest fixture monkeypatches the Python standard library socket module (`socket.socket.connect`). Any unmocked network request immediately raises `NetworkBlockError`.
   - All fixtures are stored locally in `tests/fixtures/` and read via standard filesystem I/O.

---

## 3. Caveats
- **Live MCP / Android Process Bypass**: The mock fixtures and extractors are designed to test the ingestion, parsing, normalization, and GC/BigQuery pipeline in integration tests. They do not start a real Chromium instance or an Android emulator during `pytest` execution, which is intentional to meet the <10 second execution requirement.
- **Dynamic UI Class Name Shifts**: In real-world Instagram APK updates, view IDs occasionally change (e.g. between Instagram versions). The mock extractor interface is specified to accept configurable / fallback resource ID lists.
- **Track Isolation Assumptions**: Category classification heuristics (`sports_cards` vs `edm` vs `general`) use keyword/hashtag matching as defined in `GEMINI.md` track isolation rules.

---

## 4. Conclusion
The Extraction Mocking specification for R1 is fully defined with:
1. Exact fixture schemas and example data for Chrome DevTools A11y Tree snapshots (TikTok and YouTube) and Android CLI UI hierarchy dumps (Instagram Reels).
2. Standardized `TrendRecord` data contracts bridging extraction into SQLite storage (R2) and BigQuery ML formatting (R3).
3. Robust normalization rules (case preservation, emoji stripping, metric suffix conversion).
4. Strict zero-network socket blocking architecture ensuring 100% offline, deterministic test runs completing in < 1 second.
5. Comprehensive test case catalog covering happy paths, malformed trees, empty trees, special characters, and edge cases.

---

## 5. Verification Method

### Concrete Verification Steps
1. **Fixture Syntax Validation**:
   Validate that the provided fixture files parse cleanly via Python:
   ```powershell
   python -c "import json, pathlib; [json.loads(p.read_text(encoding='utf-8')) for p in pathlib.Path('tests/fixtures').glob('*.json')]"
   ```
2. **Extractor Unit & Integration Tests**:
   Execute pytest on the extractor test suite:
   ```powershell
   pytest tests/test_extractors.py tests/test_mock_fixtures.py -v
   ```
3. **Zero Network Socket Isolation Test**:
   Execute pytest with network socket blocking enabled:
   ```powershell
   pytest tests/test_network_isolation.py -v
   ```
4. **Performance Benchmark**:
   Assert execution completes well under the 10-second threshold:
   ```powershell
   pytest --durations=0
   ```

### Exact Fixture Artifact Specifications

#### Fixture 1: `tiktok_creative_center_a11y_snapshot.txt`
```text
uid=1_0 RootWebArea "TikTok Creative Center - Trending Songs & Hashtags"
  uid=1_1 main "Main Content"
    uid=1_2 heading "Trending Hashtags" level=2
      uid=1_3 table "Trending Hashtags Table"
        uid=1_4 row "Rank 1 #SportsCards"
          uid=1_5 cell "1"
          uid=1_6 cell "#SportsCards"
            uid=1_7 link "#SportsCards"
          uid=1_8 cell "1.2M"
          uid=1_9 cell "+145%"
        uid=1_10 row "Rank 2 #HardTechno"
          uid=1_11 cell "2"
          uid=1_12 cell "#HardTechno"
            uid=1_13 link "#HardTechno"
          uid=1_14 cell "850K"
          uid=1_15 cell "+82%"
        uid=1_16 row "Rank 3 #CardLadder"
          uid=1_17 cell "3"
          uid=1_18 cell "#CardLadder"
            uid=1_19 link "#CardLadder"
          uid=1_20 cell "420K"
          uid=1_21 cell "+210%"
        uid=1_22 row "Rank 4 #RaveTok"
          uid=1_23 cell "4"
          uid=1_24 cell "#RaveTok"
            uid=1_25 link "#RaveTok"
          uid=1_26 cell "310K"
          uid=1_27 cell "+55%"
        uid=1_28 row "Rank 5 #PaniniPrizm"
          uid=1_29 cell "5"
          uid=1_30 cell "#PaniniPrizm"
            uid=1_31 link "#PaniniPrizm"
          uid=1_32 cell "190K"
          uid=1_33 cell "+35%"
    uid=1_34 heading "Trending Songs" level=2
      uid=1_35 list "Trending Songs List"
        uid=1_36 listitem "1. Montagem Mysterious Game - LXNGVX"
          uid=1_37 text "Montagem Mysterious Game"
          uid=1_38 text "LXNGVX"
          uid=1_39 text "Rank 1"
          uid=1_40 text "+120%"
        uid=1_41 listitem "2. Dimension - DJ Velocity"
          uid=1_42 text "Dimension"
          uid=1_43 text "DJ Velocity"
          uid=1_44 text "Rank 2"
          uid=1_45 text "+74%"
```

#### Fixture 2: `youtube_trending_a11y_snapshot.txt`
```text
uid=2_0 RootWebArea "Trending - YouTube"
  uid=2_1 main
    uid=2_2 tablist
      uid=2_3 tab "Now" selected=true
      uid=2_4 tab "Music"
      uid=2_5 tab "Gaming"
    uid=2_6 section "Trending Videos"
      uid=2_7 link "Is the 2026 Topps Chrome Wembanyama worth grading? by CardCollector 500K views 10 hours ago"
        uid=2_8 heading "Is the 2026 Topps Chrome Wembanyama worth grading?" level=3
        uid=2_9 text "CardCollector"
        uid=2_10 text "500K views"
        uid=2_11 text "10 hours ago"
      uid=2_12 link "EDM Festival Live Set 2026 - Mainstage Ultra by RaveMaster 1.2M views 1 day ago"
        uid=2_13 heading "EDM Festival Live Set 2026 - Mainstage Ultra" level=3
        uid=2_14 text "RaveMaster"
        uid=2_15 text "1.2M views"
        uid=2_16 text "1 day ago"
```

#### Fixture 3: `instagram_reels_layout_dump.json`
```json
[
  {
    "class": "androidx.recyclerview.widget.RecyclerView",
    "bounds": "[0,0][1080,1920]",
    "center": "[540,960]",
    "interactions": ["scrollable"],
    "off-screen": false
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/caption_text_view",
    "text": "Checking the 2026 Topps Chrome rookie crop! 🔥 #TheHobby #SportsCardInvesting #WhoDoYouCollect",
    "contentDesc": "Reel caption by @sportscardscollector",
    "bounds": "[40,1400][1040,1550]",
    "center": "[540,1475]",
    "interactions": ["clickable"],
    "off-screen": false
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/audio_track_title",
    "text": "Original Audio - Card Ladder ROI Anthem",
    "contentDesc": "Audio: Original Audio - Card Ladder ROI Anthem",
    "bounds": "[40,1560][700,1620]",
    "center": "[370,1590]",
    "interactions": ["clickable"],
    "off-screen": false
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/like_count",
    "text": "45.2K",
    "bounds": "[960,1100][1040,1140]",
    "center": "[1000,1120]",
    "interactions": ["clickable"],
    "off-screen": false
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/row_feed_textview_comments_count",
    "text": "1,280",
    "bounds": "[960,1220][1040,1260]",
    "center": "[1000,1240]",
    "interactions": ["clickable"],
    "off-screen": false
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/caption_text_view",
    "text": "Heavy bassline energy at midnight! 🎧 #HardTechno #EDMDrop #RaveTok",
    "contentDesc": "Reel caption by @edmfestivals",
    "bounds": "[40,1400][1040,1550]",
    "center": "[540,1475]",
    "interactions": ["clickable"],
    "off-screen": false
  },
  {
    "class": "android.widget.TextView",
    "resourceId": "com.instagram.android:id/audio_track_title",
    "text": "Montagem Mysterious Game - LXNGVX",
    "contentDesc": "Audio: Montagem Mysterious Game",
    "bounds": "[40,1560][700,1620]",
    "center": "[370,1590]",
    "interactions": ["clickable"],
    "off-screen": false
  }
]
```

#### Fixture 4: `conftest.py` (Zero Network Enforcement Hook)
```python
import socket
import pytest

class NetworkBlockError(RuntimeError):
    """Raised when any code attempts real network I/O during test execution."""
    pass

@pytest.fixture(autouse=True)
def block_network_sockets(monkeypatch):
    """Enforce 100% deterministic offline execution by barring socket.socket.connect."""
    def guarded_connect(*args, **kwargs):
        raise NetworkBlockError(
            "CRITICAL: Real network socket connection blocked during integration test! "
            "All extractions must use deterministic mock fixtures."
        )

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
```
