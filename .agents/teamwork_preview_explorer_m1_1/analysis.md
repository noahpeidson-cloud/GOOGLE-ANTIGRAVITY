# Comprehensive Technical Analysis: Legacy Ingestion & Quick Share Systems

**Agent**: `teamwork_preview_explorer_m1_1`  
**Working Directory**: `d:\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_m1_1`  
**Timestamp**: 2026-09-04T23:50:00Z  
**Target Scope**:
- `d:\GOOGLE ANTIGRAVITY\content_creation\quick_share_ai_loop`
- `d:\GOOGLE ANTIGRAVITY\content_creation\ingestion_pipeline`
- `d:\GOOGLE ANTIGRAVITY\content_creation\media_pipeline`
- `d:\GOOGLE ANTIGRAVITY\content_creation\samsung_ingest.py`
- `d:\GOOGLE ANTIGRAVITY\content_creation\ingest_assets.py`
- Discovered legacy watchers: `ingest_watcher.py`, `file_locker.py`, `inbox_watchdog.py`, `proxy_generator.py`

---

## Executive Summary

Across the media creation codebase in `GOOGLE ANTIGRAVITY`, ingestion mechanisms evolved through three distinct generations:
1. **Ad-hoc Desktop Automation (Gen 1)**: `quick_share_hijack.py`, `inbox_watchdog.py`. Built around Windows desktop filesystem watchers polling Google Quick Share or Google Drive inbox directories. Highly fragile due to manual UI prompts, Wi-Fi Direct drops, unhandled socket collisions, and naive sleep-based write detection.
2. **Monolithic Scripting (Gen 2)**: `samsung_ingest.py` (1,432 lines) and `ingest_assets.py` (806 lines). Introduced sophisticated mDNS discovery, ffprobe stream inspection, HDR detection, canonical naming, and directory health partitioning. However, it suffered from blocking interactive console prompts (`input()`), syntax/variable bugs (`remote_md6`, `o.environ`), and tight coupling.
3. **Resilient Distributed Ingestion Engine (Gen 3)**: `media_pipeline/ingestion/` (`adb_connection_manager.py`, `ingestion_daemon.py`, `manifest_store.py`, `gcs_uploader.py`). Industrial-grade, fully test-driven architecture featuring Samsung One UI 6+ Auto Blocker bypass, on-device `sha256sum` cross-airgap verification, 2-tick active recording guards, cross-platform OS process locking, atomic `.part` downloads with quarantine isolation, and SQLite state tracking.

This report evaluates each target subsystem, isolates systemic failure modes, separates proven engineering gems from legacy boilerplate, and provides exact frontmattered specifications for long-term archiving in `_archive_vault`.

---

## Section 1: Detailed Subsystem Evaluations

### 1.1 `content_creation/quick_share_ai_loop`

#### Files Inspected:
- `quick_share_hijack.py` (117 lines)
- `gemini_tagger.py` (108 lines)
- `database_sink.py` (270 lines)
- `schema.sql` (2,631 bytes) & `schema.gql` (936 bytes)
- `tests/test_database_sink.py` (34 tests), `tests/test_adversarial_pool.py` (34 tests), `tests/test_adversarial_payloads.py` (27 tests)

#### Architecture & Intended Behavior:
A watchdog observer monitors `~/Downloads/Quick Share` for incoming `.mp4`/`.mov`/`.webm` videos sent from mobile devices. When file writing ceases, it invokes `gemini_tagger.py` to transcode a 720p proxy and extract a 4-layer taxonomy via Gemini, sinks analytics to PostgreSQL (`database_sink.py`), and transfers the master file to `G:/My Drive/.../Raw_Ingest` with SHA-256 validation before deleting the original from C:.

#### Observed Failure Modes & Weaknesses:
1. **Transport Layer Flaw (Rule R35 Violation)**:
   Quick Share (formerly Nearby Share) is a proprietary, UI-driven utility requiring interactive desktop/mobile approval popups. Under 4K/8K multi-gigabyte loads (e.g. 10GB-50GB concert takes), the Wi-Fi Direct connection frequently drops or caps transfer rates, leaving partial files.
2. **Brittle File Completion Heuristic (`quick_share_hijack.py:16-40`)**:
   ```python
   def wait_for_file_to_finish(filepath, timeout=300):
       # If current_size > 0 and hasn't changed in 3 seconds, it's done writing.
       if current_size > 0 and current_size == historical_size:
           try:
               with open(filepath, 'a'):
                   return True
           except IOError:
               pass
       historical_size = current_size
       time.sleep(3)
   ```
   - If network packets or disk buffering pause write activity for 3 seconds, `current_size == historical_size` triggers prematurely, leading to ingestion of truncated media.
   - `open(filepath, 'a')` in append mode attempts to write to the file; if the writer opened the file with shared permissions (`FILE_SHARE_READ | FILE_SHARE_WRITE`), the append check succeeds even while writing continues.
3. **Synchronous Execution in Watchdog Thread**:
   The `on_created` handler synchronously executes `tag_video()` (which can take 30-90s) and file hashing. If multiple files are dropped in batch, the watchdog event loop blocks or drops queue events.
4. **Hardcoded G: Drive Dependency (`quick_share_hijack.py:14`)**:
   `FINAL_DESTINATION = Path("G:/My Drive/GOOGLE ANTIGRAVITY/photos_triage_project/Raw_Ingest")`. If Google Drive Desktop is unmounted or disconnected, this crashes (violating Rule R19).
5. **No Boot Ingress Recovery**:
   Existing files sitting in the directory when the script starts are ignored because the script relies entirely on `on_created` events.
6. **Gemini Tagger Infinite Loop & Error Handling Weakness (`gemini_tagger.py:45-52, 66-98`)**:
   ```python
   while True:
       file_info = client.files.get(name=uploaded_file.name)
       if file_info.state.name == "ACTIVE":
           break
       elif file_info.state.name == "FAILED":
           raise Exception("Video processing failed.")
       time.sleep(5)
   ```
   - No polling timeout: if the Gemini File API stalls in `PROCESSING`, the loop hangs indefinitely.
   - In 429/503 retry handling, it uses exponential `time.sleep()`, violating Rule R27 (The Zero-Friction Fallback Mandate) which mandates tiered model cascades.
   - Creates temporary proxy in source directory (`parent / "temp_proxy"`), failing if source media is on a read-only filesystem.

#### High-Value Gems in this Module:
- **`database_sink.py`**:
  - Thread-safe connection pooling (`psycopg2.pool.ThreadedConnectionPool`).
  - Pre-ping connection health validation (`SELECT 1;`) to transparently recover from silent Cloud SQL / NAT proxy TCP drops.
  - Context manager `get_db_connection()` with guaranteed rollback on exception and `putconn(conn, close=is_broken)` on broken sockets.
  - Explicit TCP keepalives (`keepalives=1`, `keepalives_idle=30`, `keepalives_interval=10`, `keepalives_count=3`).
  - Native parameterized JSONB upsert with `ON CONFLICT (filename) DO UPDATE`.
  - Fail-fast environment validation adhering to Rule R26.
  - Comprehensive adversarial test suite with 95 passing unit and integration tests.
- **Fast FFmpeg Proxy Generation (`gemini_tagger.py:13-31`)**:
  - Automatically locates bundled binary via `imageio_ffmpeg.get_ffmpeg_exe()`.
  - Downscales to 720p 30fps at 1Mbps video / 128kbps audio, slashing multi-GB video uploads down to lightweight payloads.

---

### 1.2 `content_creation/ingestion_pipeline`

#### Files Inspected:
- `edge/usb_ingest_daemon.py` (94 lines)
- `pipeline.py` (27 lines)
- `test_pipeline.py` (877 bytes)
- `orchestrator/langgraph_orchestrator.py` (58 lines)
- `dataflow/dataflow_pipeline.py` (51 lines)
- `s26_controller/` (core .py files were historically archived/moved; only `__pycache__` remained)

#### Observed Failure Modes & Weaknesses:
1. **`edge/usb_ingest_daemon.py` - Unbounded Re-Ingestion**:
   ```python
   subprocess.run(["adb", "pull", "-a", "/sdcard/DCIM/Camera/", STAGING_DIR], check=True)
   ```
   Every time the USB cable is connected, it attempts to pull the *entire* `/sdcard/DCIM/Camera/` directory. On a phone with 256GB of media, this wastes hours re-transferring existing files or causes local storage exhaustion.
2. **Destructive Data Loss Risk (`edge/usb_ingest_daemon.py:56-57`)**:
   ```python
   # Optionally: Clean up the S26 Ultra storage after successful transfer
   # subprocess.run(["adb", "shell", "rm", "-rf", "/sdcard/DCIM/Camera/*"])
   ```
   Commented command proposes wiping camera storage without bit-for-bit checksum verification!
3. **`pipeline.py` Platform Incompatibility**:
   Uses hardcoded string splitting `video_path.split("/")[-1]`, which fails on Windows backslash paths (`\` returning the entire path as filename).
4. **Boilerplate / Skeletal Implementations**:
   - `langgraph_orchestrator.py`: Stub nodes that only print strings.
   - `dataflow_pipeline.py`: Generic Apache Beam streaming boilerplate.

#### High-Value Gems in this Module:
- **WMI Physical USB Insertion Event Hook (`edge/usb_ingest_daemon.py:62-80`)**:
  ```python
  pythoncom.CoInitialize()
  c = wmi.WMI()
  watcher = c.watch_for(
      notification_type="CreationEvent",
      wmi_class="Win32_DeviceChangeEvent",
      EventType=2
  )
  ```
  Uses native Windows Management Instrumentation (WMI) event subscriptions to capture physical USB device insertion (`EventType=2`) without polling loops.
- **ADB Authorization Filter (`edge/usb_ingest_daemon.py:22-36`)**:
  Parses `adb devices` looking for `device` state while discarding `unauthorized` and `offline`.

---

### 1.3 `content_creation/media_pipeline/ingestion`

#### Files Inspected:
- `adb_connection_manager.py` (211 lines)
- `manifest_store.py` (250 lines)
- `ingestion_daemon.py` (487 lines)
- `gcs_uploader.py` (140 lines)
- `test_adversarial_ingestion.py` (807 lines)
- `test_ingestion_daemon.py` (520 lines)

#### Architecture & Intended Behavior:
A headless, production-ready daemon operating in a continuous loop under a single-instance process lock. Discovers wireless or USB ADB Android devices, scans DCIM directories in a single shell call, filters out actively recording media using a 2-tick delta check, pulls files atomically into `.part` buffers, computes local and on-device SHA-256 digests, quarantines corrupt files, and streams verified assets to Google Cloud Storage with `if_generation_match=0` preconditions.

#### Observed Failure Modes & Weaknesses:
1. **Hardcoded Subnet Defaults (`adb_connection_manager.py:26`)**:
   Defaults to `device_ip = "192.168.1.150"`. If mDNS fails or local DHCP assigns a different IP, manual reconnection is required unless mDNS resolution succeeds.
2. **Synchronous Single-Threaded Pull Loop**:
   Pulls files sequentially within each polling cycle. While robust and safe against race conditions, pulling multiple 20GB files sequentially cannot saturate a 10Gbps local Wi-Fi 7 / USB 3.2 connection.

#### High-Value Gems in this Module (Tier 1 Architecture):
1. **Samsung One UI 6+ Auto Blocker Bypass (`adb_connection_manager.py:90-117`)**:
   ```python
   # Sets rampart_auto_enabled_switch_enabled to 0
   cmd = [self.adb_binary, "-s", self.target, "shell", "settings", "put", "global", "rampart_auto_enabled_switch_enabled", "0"]
   ```
   Research-validated mitigation against Samsung's One UI 6 "Auto Blocker" security service that automatically kills ADB sessions on screen lock.
2. **On-Device Cryptographic Checksumming (`adb_connection_manager.py:197-211`)**:
   ```python
   ret, stdout, stderr = self.execute_shell(f"sha256sum '{remote_path}'", timeout=timeout)
   ```
   Runs `sha256sum` directly on Android's Linux coreutils, allowing bit-for-bit cryptographic verification across the air gap before deleting or archiving source media.
3. **2-Tick Delta Check Active Recording Guard (`ingestion_daemon.py:150-200`)**:
   ```python
   def is_actively_recording(self, device_path, current_size, current_time=None):
       # Tracks last_size, last_changed_time, and verifies growth vs stability window
       if current_size > last_size or current_size < last_size:
           tracker["stable"] = False
           return True
       if (now - tracker["last_changed_time"]) < self.min_stability_seconds:
           return True
       tracker["stable"] = True
       return False
   ```
   Mathematically sound approach to avoiding pulling incomplete or actively recording video takes without relying on inaccurate file modification timestamps.
4. **Batch Directory Stat Optimization (`ingestion_daemon.py:121-124`)**:
   ```python
   cmd = f"stat -c '%n|%s|%Y' {ext_patterns} 2>/dev/null"
   ```
   Executes a single remote shell call to stat all media files at once, reducing round-trip ADB latency from $O(N)$ shell calls to $O(1)$.
5. **Cross-Platform Single-Instance Process Lock (`ingestion_daemon.py:32-102`)**:
   Uses `msvcrt.locking` on Windows and `fcntl.flock` on Unix with PID recording to prevent duplicate daemons and split-brain states.
6. **SQLite Transactional Manifest Store (`manifest_store.py`)**:
   Tracks the complete lifecycle through 8 states:
   `DISCOVERED -> RECORDING -> DOWNLOADING -> DOWNLOADED -> HASH_VERIFIED -> UPLOADING -> GCS_CONFIRMED (or FAILED / QUARANTINED)`.
7. **Atomic Staging & Quarantine (`ingestion_daemon.py:270-349`)**:
   Transfers to `.part` file. If local SHA-256 != remote SHA-256, moves file to `quarantine/corrupt_{file_name}_{timestamp}.part`, records status `QUARANTINED` in SQLite, and raises `CryptographicIntegrityError`.
8. **Resumable GCS Uploader (`gcs_uploader.py`)**:
   Enforces idempotency using `if_generation_match=0`, verifies client/server CRC32c, and attaches custom metadata (`x-goog-meta-sha256`).

---

### 1.4 `content_creation/samsung_ingest.py`

#### Architecture & Intended Behavior:
A 1,432-line standalone ingestion bridge designed to connect Samsung Galaxy S26 Ultra phones directly to the Track 2 EDM pipeline via wireless or wired ADB.

#### Observed Failure Modes & Fatal Bugs:
1. **Interactive Blocking Prompt in Headless Execution (`samsung_ingest.py:1181`)**:
   ```python
   while True:
       sel = input("\nEnter assets to pull (e.g. '1', '1,2-4', 'all', 'none'): ").strip().lower()
   ```
   When invoked via background agent, headless script, or task scheduler, `input()` permanently blocks on stdin or throws `EOFError: EOF when reading a line`, crashing execution!
2. **Syntax NameErrors (Undetected Runtime Bugs)**:
   - Line 1270: `print(f"  [REMOTE MD5] {asset.filename}: {remote_md6}")` — Variable `remote_md6` is misspelled (should be `remote_md5`). Enabling `--verify-remote-md5` triggers `NameError: name 'remote_md6' is not defined`.
   - Line 96: `return Path(o.environ[env_var])` in fallback `find_binary` — `o` is undefined (should be `os`).
3. **Flawed Active Recording Detection (`samsung_ingest.py:774`)**:
   ```python
   if (now_epoch - mtime_epoch) < 5.0:
       continue
   ```
   - On Android devices, camera video files often set `mtime` at file creation time or only upon container finalization.
   - If the host system clock and phone clock differ by more than 5 seconds, this check completely breaks.
4. **Heavy Coupling**:
   Directly imports `config.py` and `ingest_assets.py` with massive fallback exception handling blocks, leading to code duplication.

#### High-Value Gems in this Module:
1. **Python Zeroconf mDNS Discovery (`samsung_ingest.py:284-486`)**:
   - Implements `ADBMDNSDiscovery` and `ADBMDNSListener` using `zeroconf` to listen on `_adb-tls-connect._tcp.local.` and `_adb._tcp.local.`.
   - `extract_ip_address()` reliably handles `parsed_addresses()`, raw 4-byte IPv4 arrays, and 16-byte IPv6 arrays across diverse `zeroconf` library versions.
   - `parse_service_properties()` properly decodes binary TXT records into clean string dictionaries.
   - Filters and prioritizes Samsung S26 Ultra flagships (models matching `SM-S948*`).
2. **Deep Binary Discovery Engine (`samsung_ingest.py:492-550`)**:
   Resolves `adb` across CLI args, environment variables (`ADB_BINARY`, `ANDROID_HOME`, `ANDROID_SDK_ROOT`), system PATH, Scoop, LocalAppData, and standard Program Files locations.
3. **Dynamic File-Size-Weighted Timeout (`samsung_ingest.py:811-813`)**:
   ```python
   size_gb = expected_size_bytes / (1024 * 1024 * 1024)
   calc_timeout = max(ADB_DEFAULT_TIMEOUT_SECONDS, size_gb * ADB_PULL_TIMEOUT_PER_GB_SECONDS)
   ```
   Scales timeout dynamically based on file size, preventing timeout crashes on 50GB 8K takes while failing fast on small files.
4. **Host Capacity & Headroom Check (`samsung_ingest.py:1224-1233`)**:
   Uses `shutil.disk_usage` to assert that host disk capacity has enough space for pending transfers plus a mandatory 5GB safety headroom (`ADB_MIN_FREE_DISK_HEADROOM_BYTES`).
5. **Multi-Tier Deduplication Ledger (`samsung_ingest.py:860-910, 1038-1070`)**:
   Verifies deduplication across three independent tiers: `.adb_ingest_ledger.json`, 4-tier directory scanning, and SQLite `asset_manifest`.

---

### 1.5 `content_creation/ingest_assets.py`

#### Architecture & Intended Behavior:
An 806-line media stream inspection, canonical renaming, and 4-tier directory routing utility.

#### Observed Failure Modes & Weaknesses:
1. **Hardcoded Winget Path Coupling in Caller Scripts**:
   Callers (e.g. `inbox_watchdog.py`) pass hardcoded WinGet paths (`C:\Users\noahp\AppData\Local\Microsoft\WinGet\...`), breaking portability across different machines.
2. **Sequential Probing**:
   Probing multiple incoming files runs sequentially via subprocess; running ffprobe concurrently across batch drops would be significantly faster.

#### High-Value Gems in this Module (Industry-Standard Media Engineering):
1. **Precision Stream Telemetry Extraction (`ingest_assets.py:185-318`)**:
   - Executes `ffprobe -v error -show_format -show_streams -print_format json`.
   - Computes accurate constant frame rate (CFR) by evaluating the rational fraction `r_frame_rate` (num / den).
   - Computes aspect ratio dynamically using the greatest common divisor (`_compute_gcd(width, height)`).
   - Robust **HDR Detection**:
     Evaluates color transfer characteristics (`arib-std-b67` [HLG], `smpte2084` [PQ/HDR10], `bt2020-10`, `bt2020-12`), color primaries (`bt2020`), and pixel formats (`hdr`, `10le`).
2. **Canonical Filename Normalization & DJ Character Transliteration (`ingest_assets.py:331-402`)**:
   - Canonical naming syntax: `YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`.
   - Normalizes European Latin DJ characters (`Ø -> O`, `ø -> o`, `Æ -> Ae`, `æ -> ae`, `ß -> ss`, `Ł -> L`, `ł -> l`, `Đ -> D`, `đ -> d`).
   - Uses `unicodedata.normalize("NFKD", ...)` to strip combining diacritics (`ë -> e`, `ö -> o`), producing strictly clean ASCII tokens for filesystem safety.
3. **Directory Health Guard (`ingest_assets.py:407-443`)**:
   - Enforces a maximum 50-item limit per directory.
   - If `subfolder_slug` reaches 50 items, automatically overflows into `subfolder_slug_Batch02`, `subfolder_slug_Batch03`, etc., preventing Google Drive sync freezes and OS file-indexing bottlenecks.
4. **Zero-Copy File Promotion (`ingest_assets.py:580-585`)**:
   Attempts an OS hard link (`os.link(src, staged_file_path)`) for instant zero-disk-overhead promotion, falling back to `shutil.copy2` only if crossing filesystem boundaries.
5. **Self-Documenting Ingestion Manifest**:
   Generates `ingestion_manifest.json` per take containing complete probe telemetry, project ID, brand, tier, source path, staged path, and duration warnings.

---

### 1.6 Additional Discovered Watchers & Utilities

#### Files Inspected:
- `D:\GOOGLE ANTIGRAVITY\archive\c_drive_legacy\teamwork_projects\baptism_of_music_brain\src\watcher\file_locker.py` (378 lines)
- `D:\GOOGLE ANTIGRAVITY\archive\c_drive_legacy\teamwork_projects\baptism_of_music_brain\src\watcher\ingest_watcher.py` (241 lines)
- `content_creation\inbox_watchdog.py` (103 lines)
- `content_creation\proxy_generator.py` (108 lines)

#### Key Insights:
- **`file_locker.py` - 3-Tier Windows File Lock Detector**:
  - **Tier 1**: Extension filter excluding `.tmp`, `.part`, `.crdownload`, `~$`, etc.
  - **Tier 2**: Native Win32 Exclusive Handle Acquisition (`win32file.CreateFile` with `dwShareMode=0`). Checks for `ERROR_SHARING_VIOLATION` (32) and `ERROR_LOCK_VIOLATION` (33). On `ERROR_ACCESS_DENIED` (5), gracefully retries with `GENERIC_READ` and `dwShareMode=0` to verify read-only files.
  - **Tier 3**: File size stability debounce.
  - *Synthesis*: Combining `file_locker.py`'s Win32 exclusive handle check with `ingestion_daemon.py`'s 2-tick delta check creates the ultimate lock-detection engine.
- **`proxy_generator.py`**:
  - Uses `ProcessPoolExecutor` capped to `min(multiprocessing.cpu_count(), 8)` for parallel FFmpeg proxy generation, followed by a single-threaded SQLite update pass to avoid database locking.

---

## Section 2: Synthesis — Gold vs. Boilerplate

| Subsystem / File | Classification | Core Rationale | Action for Archive Vault |
|---|---|---|---|
| `quick_share_ai_loop/quick_share_hijack.py` | **Flawed / Brittle** | Closed UI transport, 3s static sleep bug, hardcoded G: drive, synchronous handler | Discard transport; retain SHA-256 verify logic |
| `quick_share_ai_loop/gemini_tagger.py` | **Partial Gold** | Fast FFmpeg proxy generator is valuable; Gemini polling loop lacks timeout; violates R27 | Extract proxy generator; discard infinite while loop |
| `quick_share_ai_loop/database_sink.py` | **Pure Gold** | ThreadedConnectionPool, pre-ping recovery, keepalive tuning, idempotent JSONB upsert, R26 fail-fast | **Extract as standalone concept** |
| `ingestion_pipeline/edge/usb_ingest_daemon.py` | **Partial Gold** | WMI event watcher is excellent; blanket ADB pull and commented wipe are dangerous | Extract WMI hardware listener; discard blanket pull |
| `ingestion_pipeline/pipeline.py` & `dataflow/` | **Boilerplate** | Hardcoded bucket stubs and standard Beam streaming templates | Discard |
| `media_pipeline/ingestion/adb_connection_manager.py` | **Pure Gold** | Samsung One UI 6+ Auto Blocker bypass, mDNS discovery, on-device `sha256sum`, backoff with jitter | **Extract as standalone concept** |
| `media_pipeline/ingestion/manifest_store.py` | **Pure Gold** | SQLite 8-state lifecycle tracking, quarantine status, transactional context manager | **Extract as standalone concept** |
| `media_pipeline/ingestion/ingestion_daemon.py` | **Pure Gold** | ProcessLock, batch stat query, 2-tick delta check, atomic .part downloads, cryptographic quarantine | **Extract as standalone concept** |
| `media_pipeline/ingestion/gcs_uploader.py` | **Pure Gold** | Resumable streaming, `if_generation_match=0` idempotency, CRC32c verification | **Extract as standalone concept** |
| `samsung_ingest.py` | **Mixed Gold & Brittle** | mDNS Zeroconf engine, binary discovery, capacity headroom, dynamic timeout are gold; `input()` prompt and `remote_md6` typo are fatal | Extract mDNS & capacity logic; discard interactive CLI |
| `ingest_assets.py` | **Pure Gold** | ffprobe stream telemetry, robust HDR detection, canonical naming, Latin character map, DirectoryHealthGuard | **Extract as standalone concepts** |
| `file_locker.py` | **Pure Gold** | Win32 native exclusive file handle test (`dwShareMode=0`) with sharing violation detection | **Extract as standalone concept** |

---

## Section 3: Exact Proposed Frontmattered Extraction Specifications

These 7 isolated concepts represent the complete extraction plan for long-term storage in `_archive_vault`.

---

### Concept 1: `concept_adb_lifecycle_and_autoblocker_bypass`
- **File Name**: `concept_adb_lifecycle_and_autoblocker_bypass.py`
- **Context Mapping**: Derived from `content_creation/media_pipeline/ingestion/adb_connection_manager.py` and `samsung_ingest.py`. Used for zero-touch physical and wireless ADB media ingress from Android flagships (Samsung Galaxy S22-S26 Ultra).
- **Strengths**:
  - Mitigates Samsung One UI 6+ Auto Blocker lockout timer via `settings put global rampart_auto_enabled_switch_enabled 0`.
  - Executes on-device cryptographic verification via `sha256sum '{remote_path}'` directly in Android Linux shell.
  - Implements exponential backoff with random jitter to survive Wi-Fi drops.
  - Supports dependency-injected `command_executor` for 100% deterministic mocking.
- **Weaknesses**:
  - Requires developer options and USB/wireless debugging enabled on the target device.
  - On Samsung One UI, initial pairing still requires a one-time RSA fingerprint authorization on screen.
- **Implementation Instructions**:
  Instantiate `AdbConnectionManager(device_ip, device_port)`. Call `ensure_connected()` before any transfer cycle. For remote hashing, call `get_remote_file_sha256(remote_path)` to obtain the authoritative ground-truth hash before pulling bytes.

---

### Concept 2: `concept_active_recording_guard`
- **File Name**: `concept_active_recording_guard.py`
- **Context Mapping**: Synthesized from `content_creation/media_pipeline/ingestion/ingestion_daemon.py:IncrementalMediaScanner` and `archive/.../file_locker.py`. Replaces fragile sleep checks and mtime filters.
- **Strengths**:
  - 2-Tick Size Delta Check detects file growth across polling ticks, ensuring files actively being recorded by the camera are not ingested prematurely.
  - Win32 native exclusive handle check (`win32file.CreateFile` with `dwShareMode=0`) verifies OS lock release on host filesystem drops, detecting `ERROR_SHARING_VIOLATION` (32) and `ERROR_LOCK_VIOLATION` (33).
  - Handles read-only media gracefully via `GENERIC_READ` fallback.
- **Weaknesses**:
  - Requires at least 2 consecutive observation ticks separated by `min_stability_seconds` (default 3.0s), adding a slight initial latency to ingress.
- **Implementation Instructions**:
  For remote Android files, use `IncrementalMediaScanner(adb_manager).is_actively_recording(path, size)`. For local drops (e.g. Syncthing, SMB, or USB staging), call `test_exclusive_handle(local_path)` and verify `LockCheckResult.is_ready`.

---

### Concept 3: `concept_cryptographic_quarantine_ingestion_engine`
- **File Name**: `concept_cryptographic_quarantine_ingestion_engine.py`
- **Context Mapping**: Derived from `content_creation/media_pipeline/ingestion/ingestion_daemon.py` and `manifest_store.py`. Manages physical/wireless media transfer to staging storage.
- **Strengths**:
  - Enforces atomic `.part` buffer staging (`filename.part` -> verify hash -> `os.rename`).
  - Bit-for-bit SHA-256 comparison between local stream hash and on-device remote hash.
  - On mismatch or corruption, automatically isolates corrupt buffer into a dedicated `quarantine/` folder for forensic inspection and flags manifest state as `QUARANTINED`.
  - Transactional SQLite manifest tracking: `DISCOVERED -> RECORDING -> DOWNLOADING -> DOWNLOADED -> HASH_VERIFIED -> UPLOADING -> GCS_CONFIRMED (or FAILED / QUARANTINED)`.
  - Single-instance process lock (`msvcrt` on Windows / `fcntl` on Linux) preventing duplicate concurrent daemons.
- **Weaknesses**:
  - Cryptographic verification on 50GB 8K files consumes significant CPU cycles; requires chunked buffer streaming (64KB chunks).
- **Implementation Instructions**:
  Initialize `ManifestStore(db_path)` and `IngestionDaemon(...)`. Run under `ProcessLock(lock_file_path)`. Call `run_cycle()` inside a supervised polling loop.

---

### Concept 4: `concept_ffprobe_stream_telemetry_and_hdr_detector`
- **File Name**: `concept_ffprobe_stream_telemetry_and_hdr_detector.py`
- **Context Mapping**: Derived from `content_creation/ingest_assets.py:probe_media_file`. Foundation for downstream video processing, proxy generation, and DaVinci Resolve color grading.
- **Strengths**:
  - Computes true constant frame rate (CFR) by evaluating rational fraction `r_frame_rate` (num / den).
  - Computes aspect ratio dynamically via GCD (`_compute_gcd(width, height)`).
  - Comprehensive HDR detection: checks color transfer (`arib-std-b67` [HLG], `smpte2084` [PQ/HDR10], `bt2020-10`, `bt2020-12`), color primaries (`bt2020`), and pixel format (`hdr`, `10le`).
  - Emits dataclass `StreamProbeData` containing resolution label (`4k`, `1080p`, `720p`), audio channels, bitrates, sample rates, and duration.
- **Weaknesses**:
  - Requires `ffprobe` binary present on system PATH or specified via environment variable.
- **Implementation Instructions**:
  Call `probe_media_file(file_path, ffprobe_path=None)`. Inspect `probe_data.is_hdr` to route HDR footage to mobius tone-mapping or ACES color pipelines.

---

### Concept 5: `concept_canonical_media_normalizer`
- **File Name**: `concept_canonical_media_normalizer.py`
- **Context Mapping**: Derived from `content_creation/ingest_assets.py:FilenameNormalizer`. Enforces consistent naming grammar across multi-platform content pipelines.
- **Strengths**:
  - Canonical grammar: `YYYYMMDD_[Event]_[Artist]_[TrackName-or-ID]_V[#]_[Resolution].mp4`.
  - Full bidirectional parsing via named regex groups (`date`, `event`, `artist`, `track`, `version`, `resolution`, `ext`).
  - DJ Latin character map (`Ø -> O`, `ø -> o`, `Æ -> Ae`, `æ -> ae`, `ß -> ss`, `Ł -> L`, `ł -> l`, `Đ -> D`, `đ -> d`).
  - NFKD Unicode normalization decomposing diacritics (`ë -> e`, `ö -> o`, `é -> e`), guaranteeing cross-platform filesystem safety.
- **Weaknesses**:
  - Destructive to non-Latin scripts (e.g. Cyrillic, Kanji, Arabic) if not transliterated before token sanitization.
- **Implementation Instructions**:
  Use `FilenameNormalizer.build_canonical_filename(...)` when generating staged filenames. Use `FilenameNormalizer.parse_filename(...)` to reverse-engineer metadata from existing assets.

---

### Concept 6: `concept_directory_health_partitioner`
- **File Name**: `concept_directory_health_partitioner.py`
- **Context Mapping**: Derived from `content_creation/ingest_assets.py:DirectoryHealthGuard`. Solves cloud sync (Google Drive / OneDrive) and IDE file-indexing latency.
- **Strengths**:
  - Enforces a hard capacity ceiling (default: 50 items) per directory.
  - Automatically partitions overflowing directories into batch folders (`slug_Batch02`, `slug_Batch03`, etc.).
  - Completely eliminates file explorer hangs and cloud synchronization queue stalls.
- **Weaknesses**:
  - Downstream consumers must search across batch partitions (e.g. using `rglob` or recursive directory scanning).
- **Implementation Instructions**:
  Call `guard = DirectoryHealthGuard(max_items=50)`. Obtain target staging paths via `guard.get_healthy_subfolder(base_dir, project_slug)`.

---

### Concept 7: `concept_postgresql_resilient_database_sink`
- **File Name**: `concept_postgresql_resilient_database_sink.py`
- **Context Mapping**: Derived from `content_creation/quick_share_ai_loop/database_sink.py`. Powers media metadata and analytics syncing to Cloud SQL / PostgreSQL / Firebase Data Connect.
- **Strengths**:
  - `ThreadedConnectionPool` singleton with safe context manager (`get_db_connection()`).
  - Pre-ping connection recovery (`SELECT 1;`) that silently drops and recovers dead TCP sockets before execution.
  - TCP keepalives configured for aggressive proxy/NAT timeout survival.
  - Native parameterized JSONB upsert with `ON CONFLICT (filename) DO UPDATE`.
  - Automatic transaction rollback on exceptions and guaranteed `putconn(conn, close=is_broken)`.
  - Adheres strictly to Rule R26 (fail-fast environment variable validation).
- **Weaknesses**:
  - Requires PostgreSQL backend and `psycopg2-binary` library.
- **Implementation Instructions**:
  Configure `.env` with `PG_HOST`, `PG_USER`, `PG_PASSWORD`, `PG_DB`. Call `init_db()` once at startup. Sync records using `insert_video_analytics(filepath, tags_json)`.

---

## Section 4: Extraction Recommendations & Vault Architecture

1. **Target Vault Location**:
   `d:\GOOGLE ANTIGRAVITY\content_creation\_archive_vault`
2. **File Structure in Vault**:
   ```
   _archive_vault/
   ├── concept_adb_lifecycle_and_autoblocker_bypass.py
   ├── concept_active_recording_guard.py
   ├── concept_cryptographic_quarantine_ingestion_engine.py
   ├── concept_ffprobe_stream_telemetry_and_hdr_detector.py
   ├── concept_canonical_media_normalizer.py
   ├── concept_directory_health_partitioner.py
   └── concept_postgresql_resilient_database_sink.py
   ```
3. **Execution Guardrail**:
   In accordance with the Zero-Modification Guarantee and Rule R3, no source files in `content_creation` have been altered or deleted. The extracted concepts can be ported cleanly by the synthesizer / implementer agent into the `_archive_vault`.
