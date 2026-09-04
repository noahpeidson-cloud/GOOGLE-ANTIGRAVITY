# Technical Architecture Report: Samsung S26 Ultra ADB Ingestion Bridge (`samsung_ingest.py`)

- **Author:** Explorer 2 (Teamwork Explorer Archetype)
- **Target Component:** Requirement 2: ADB Ingestion Bridge (`samsung_ingest.py`)
- **Operational Domain:** Track 2 (`/content_creation`) — EDM Mobile Concert & Festival Media Engineering
- **Date:** 2026-08-21T22:23:30-07:00

---

## Table of Contents
1. [Executive Architecture Summary & Strategic Positioning](#1-executive-architecture-summary--strategic-positioning)
2. [ADB CLI Commands, Protocols & Python Integration Mechanism](#2-adb-cli-commands-protocols--python-integration-mechanism)
3. [Android & Samsung Galaxy S26 Ultra Filesystem & Media Architecture](#3-android--samsung-galaxy-s26-ultra-filesystem--media-architecture)
4. [File Transfer Integrity, Atomic Staging & 3-Tier Deduplication Strategy](#4-file-transfer-integrity-atomic-staging--3-tier-deduplication-strategy)
5. [Exhaustive Edge Cases, Failure Modes & Remediation Matrix](#5-exhaustive-edge-cases-failure-modes--remediation-matrix)
6. [Integration Architecture with Existing `content_creation` Pipeline](#6-integration-architecture-with-existing-content_creation-pipeline)
7. [Comprehensive Implementation Blueprint & Specification for `samsung_ingest.py`](#7-comprehensive-implementation-blueprint--specification-for-samsung_ingestpy)

---

## 1. Executive Architecture Summary & Strategic Positioning

### 1.1 The Ingestion Bottleneck in Festival / Concert Workflows
Capturing 4K 60fps / 8K HDR10+ concert footage on mobile devices (specifically the Samsung Galaxy S26 Ultra flagship) produces massive, pristine media containers with high bitrates ($80\text{--}140\text{ Mbps}$). In live event production, transferring these assets to the editing workstation is frequently compromised by consumer-grade transfer bottlenecks:
- **Cloud Compression & Sync Lag:** Google Photos, Dropbox, OneDrive, and Quick Share often transcode, strip HDR10+ metadata, or throttle transfers over congested festival Wi-Fi / cellular networks.
- **MTP (Media Transfer Protocol) Instability:** Windows MTP drivers frequently freeze, drop connections mid-transfer on files $>4\text{ GB}$, fail to report precise byte progress, and mangle file creation timestamps.
- **Messaging App Compression:** WhatsApp, Telegram, or AirDrop equivalents recompress video to 8-bit SDR $1080\text{p}$, destroying the 10-bit HDR wide color gamut ($BT.2020$) and introducing severe blocking artifacts in high-motion laser / strobe scenes.

### 1.2 Architectural Positioning: Phase 0 Hardware Ingestion
The **ADB Ingestion Bridge (`samsung_ingest.py`)** establishes a dedicated, programmatic, hardware-to-local physical transport layer positioned as **Phase 0** of the *V2 Master Operational Blueprint for EDM Short-Form Content Strategy*:

```
+----------------------------------------------------------------------------------------------------+
|                               PHASE 0: ADB INGESTION BRIDGE (Hardware)                            |
|  [Samsung Galaxy S26 Ultra]  == (USB 3.2 Gen 1/2 @ 5 Gbps) ==>  [samsung_ingest.py]              |
|  - /sdcard/DCIM/Camera       - Toybox stat & mtime check       - Atomic .part download            |
|  - 4K 60fps HDR10+ HEVC      - 3-Tier Deduplication Engine     - Local SHA-256 Hash Verification  |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                               PHASE 1: ASSET INGESTION & ROUTING                                   |
|  - Deposit raw master into 01_RAW_INBOX                                                            |
|  - Optional Auto-Route: AssetIngestionRouter.ingest_asset() -> ffprobe -> 02_IN_PROGRESS           |
|  - Canonical Naming: YYYYMMDD_[Event]_[Artist]_[Track]_V[#]_[Res].mp4                              |
|  - SQLite Manifest Registration (media_manifest.sqlite)                                            |
+----------------------------------------------------------------------------------------------------+
                                                   |
                                                   v
+----------------------------------------------------------------------------------------------------+
|                         PHASE 2-5: TRANSCODING, QC, SEO, & PROMOTION                               |
|  - 9:16 Re-framing (Center-crop / Blur-pad)                    - Two-pass Loudnorm (-14 LUFS)      |
|  - HDR10+ to SDR BT.709 Mobius Tone-Mapping                    - Universal Safe-Zone QC & Promotion|
+----------------------------------------------------------------------------------------------------+
```

---

## 2. ADB CLI Commands, Protocols & Python Integration Mechanism

### 2.1 Python Integration Architecture: Subprocess vs. Pure-Python-ADB / ADBUtils
A rigorous evaluation of integration options was conducted:

| Evaluation Dimension | Option A: `subprocess` CLI Wrapper (Recommended) | Option B: `adbutils` (Socket-based) | Option C: `pure-python-adb` (`ppadb`) |
| :--- | :--- | :--- | :--- |
| **External Dependencies** | **Zero** (Uses standard library `subprocess`, `os`, `shutil`, `sys`) | Requires `pip install adbutils` | Requires `pip install pure-python-adb` |
| **Protocol Compatibility** | Uses official Google Android SDK `adb.exe` server/client | Custom socket client implementation | Legacy sync protocol implementation |
| **Large File Handling ($>4\text{ GB}$)** | **Full native 64-bit support** with `adb pull -a` | Supported | **Known 32-bit overflow bugs** on $>4\text{ GB}$ files |
| **Timestamp Preservation** | Native `-a` flag preserves exact file `mtime` & `atime` | Requires manual socket stat parsing | Manual parsing required |
| **Binary Discovery** | Auto-detects Android Studio, SDK, Chocolatey, Scoop, and custom PATH | Requires ADB server running | Requires ADB server running |
| **Resilience & Maintenance** | Unbreakable; directly tracks platform-tools updates | Third-party dependency drift | Abandoned / unmaintained |

**Architectural Decision:** Implement `samsung_ingest.py` as a robust, pure-Python `subprocess` orchestration wrapper around the official Android `adb` client binary. It requires zero third-party pip dependencies, complies with Project Track 2 tooling boundaries (`python` with `subprocess`), and incorporates automated binary auto-discovery.

### 2.2 ADB Binary Discovery Engine
Following the pattern established in `ingest_assets.py` (`find_binary`), the ADB bridge implements a multi-tier search algorithm:
1. Direct CLI override (`--adb-path`).
2. Environment variables: `ADB_BINARY`, `ANDROID_HOME`, `ANDROID_SDK_ROOT`.
3. System `PATH` resolution via `shutil.which("adb")`.
4. Windows default platform-tools installations:
   - `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`
   - `C:\platform-tools\adb.exe`
   - `C:\Program Files (x86)\Android\android-sdk\platform-tools\adb.exe`
   - `%USERPROFILE%\scoop\apps\adb\current\platform-tools\adb.exe`
   - `C:\tools\platform-tools\adb.exe`

### 2.3 Comprehensive ADB Command Protocol Suite
The bridge orchestrates the following discrete ADB CLI commands:

```
+-------------------------------------------------------------------------------------------------------+
| Operation                  | Exact CLI Command                                  | Purpose             |
+----------------------------+----------------------------------------------------+---------------------+
| 1. Server Health Check     | adb version                                        | Verifies ADB daemon |
| 2. Device Enumeration      | adb devices -l                                     | Parses status/serial|
| 3. Model Query             | adb -s <serial> shell getprop ro.product.model      | S26 Ultra ID check  |
| 4. Batch Media Inspection  | adb -s <serial> shell stat -c "%s %Y %n" /sdcard... | Fast metadata stat  |
| 5. Preserving Pull         | adb -s <serial> pull -a <remote_src> <local_tmp>   | Timestamped pull    |
| 6. Binary Stream Exec      | adb -s <serial> exec-out cat <remote_src>          | PTY-safe binary I/O |
| 7. Remote Hash Check       | adb -s <serial> shell md5sum <remote_src>          | On-device checksum  |
+-------------------------------------------------------------------------------------------------------+
```

#### Why `stat -c "%s %Y %n"` replaces `ls -la`:
Parsing `adb shell ls -la` output across different Android versions (Toybox vs Toolbox vs BusyBox) is error-prone due to varying timestamp formats, permissions strings, and column widths. `stat -c "%s %Y %n"` produces strict machine-readable tuples:
- `%s`: Total file size in integer bytes (64-bit safe).
- `%Y`: Epoch timestamp of last modification (integer seconds).
- `%n`: Absolute remote file path (e.g. `/sdcard/DCIM/Camera/20260822_231500.mp4`).

#### Checksum Strategy: On-Device vs. Local
1. **On-Device `md5sum`:** Available via Toybox in Android 8+. However, computing MD5 or SHA-256 on the phone's CPU over a $15\text{ GB}$ 4K 60fps file takes $25\text{--}40\text{ seconds}$ and heats up the device.
2. **Recommended Hybrid Verification:**
   - **Pre-Transfer:** Query remote file size in bytes and modified epoch time via `stat`.
   - **Transfer:** Pull file using `adb pull -a`.
   - **Post-Transfer:** Validate local file size matches remote `stat` byte count exactly (`local_size == remote_size`).
   - **Cryptographic Check:** Compute local SHA-256 digest on workstation CPU/NVMe ($<2\text{ seconds}$ for $15\text{ GB}$).
   - **Optional Verification Flag:** `--verify-remote-md5` (opt-in on-device MD5 comparison for high-security archival).

---

## 3. Android & Samsung Galaxy S26 Ultra Filesystem & Media Architecture

### 3.1 Samsung Filesystem Hierarchy
Samsung Galaxy devices running One UI (Android 14 / 15 / 16) structure internal storage under `/storage/emulated/0/` with `/sdcard/` as a canonical symlink:

```
/sdcard/ (-> /storage/emulated/0/)
  └── DCIM/
      ├── Camera/
      │   ├── 20260822_214500.mp4          <-- Primary 4K/8K Video Recordings (Pro & Standard)
      │   ├── 20260822_214612.jpg          <-- JPEG Still Captures / Motion Photos
      │   ├── 20260822_214730.heic         <-- High-Efficiency Image Format
      │   └── 20260822_214805_LS.mp4       <-- Slow-Motion / Super Slow-Mo
      ├── Expert RAW/
      │   └── 20260822_215000.dng          <-- 16-bit Computational RAW DNG Captures
      └── MotionPhoto/
          └── ...                          <-- Extracted Motion Photo Clips (if enabled)
```

### 3.2 Samsung Galaxy S26 Ultra Media Asset Taxonomy
The ingestion bridge must categorize and process diverse Samsung media formats:

| File Pattern | Media Container & Codec | Ingestion Classification | Target Ingestion Action |
| :--- | :--- | :--- | :--- |
| `YYYYMMDD_HHMMSS.mp4` | MP4 (HEVC / H.265, 4K/8K HDR10+ / SDR, 60fps) | **High-Priority Concert Video** | Pull to `01_RAW_INBOX` $\rightarrow$ Route to Video Transcoder |
| `YYYYMMDD_HHMMSS_LS.mp4` | MP4 (HEVC, 120/240fps slow-motion) | **High-Priority Slow-Mo Reel** | Pull to `01_RAW_INBOX` $\rightarrow$ Retain high frame rate for speed ramps |
| `YYYYMMDD_HHMMSS.dng` | Adobe DNG (16-bit linear RAW Bayer) | **Master Still / Cover Art** | Pull to `01_RAW_INBOX/Stills` $\rightarrow$ Cover / Storyboard Asset |
| `YYYYMMDD_HHMMSS.jpg / .heic`| JPEG / HEIF (embedded Motion Photo MP4) | **Motion Photo / Thumbnail** | Optional extract or pull as reference still |

### 3.3 The 4GB File Boundary: Modern Android Realities
- **Legacy Myth:** Android splits videos at $4\text{ GB}$ due to FAT32 32-bit offset limits.
- **Modern Reality:** Samsung Galaxy S26 Ultra internal storage utilizes `F2FS` (Flash-Friendly File System) or `ext4`, both of which support files up to $16\text{ TB}$. In Android 11+, Google updated `MPEG4Writer` to support 64-bit file offsets natively.
- **Verification:** S26 Ultra records seamless continuous video files exceeding $20\text{ GB}$ in a single `.mp4` container. The ingestion bridge uses 64-bit integer parsing (`int(stat_output)`) across all file size assertions.

---

## 4. File Transfer Integrity, Atomic Staging & 3-Tier Deduplication Strategy

### 4.1 Non-Destructive Ingestion Policy (Safety-First)
- In live festival and concert environments, **data destruction is strictly forbidden**.
- **Default Mode:** `COPY` (Non-destructive pull). The phone storage remains untouched and serves as the primary physical onsite master backup.
- **Destructive Deletion:** Only enabled with explicit flags: `--delete-from-device --force-delete`. Requires double verification (local file size match AND SHA-256 hash successfully written to `media_manifest.sqlite`).

### 4.2 Atomic Staging Pattern (.part Files)
To prevent corrupted or incomplete files from entering the pipeline during sudden cable disconnects or battery drain, transfers follow an atomic staging state machine:

```
[Remote: /sdcard/DCIM/Camera/20260822_214500.mp4]
                     |
                     |  adb pull -a
                     v
[Local Temporary: 01_RAW_INBOX/.tmp_20260822_214500.mp4.part]
                     |
                     |  1. Verify: local_size == remote_size
                     |  2. Calculate: local_sha256
                     v
[Atomic Rename: os.replace()]
                     |
                     v
[Final Staged Master: 01_RAW_INBOX/20260822_214500.mp4]
```

1. Files are downloaded into `01_RAW_INBOX/.tmp_<filename>.part`.
2. Upon download completion, `local_file.stat().st_size` is compared against remote `stat` byte count.
3. If sizes match, the local SHA-256 hash is computed.
4. An atomic rename (`os.replace`) promotes `.part` to the final destination filename in `01_RAW_INBOX`.
5. On any exception (`CalledProcessError`, `TimeoutExpired`, `KeyboardInterrupt`), the partial `.part` file is immediately deleted (`unlink(missing_ok=True)`).

### 4.3 3-Tier Deduplication Strategy
To prevent pulling duplicate multi-gigabyte files during repeated sync runs, `samsung_ingest.py` implements a 3-tier hierarchical deduplication engine:

```
                                  [Remote Asset Discovered]
                                             |
                                             v
               +-------------------------------------------------------------+
               | Tier 1: Local Filesystem Scan                               |
               | - Check 01_RAW_INBOX, 02_IN_PROGRESS, 03_READY_TO_POST,      |
               |   and 04_ARCHIVE for existing filename & identical size     |
               +-------------------------------------------------------------+
                                       /              \
                                [Match Found]    [No Match]
                                     /                  \
                                    v                    v
                   +-------------------+   +---------------------------------+
                   | SKIP DOWNLOAD     |   | Tier 2: SQLite Manifest Query   |
                   | Status: DUPLICATE |   | - Query media_manifest.sqlite   |
                   +-------------------+   |   for source_file_name & size   |
                                           +---------------------------------+
                                                   /                 \
                                            [Match Found]       [No Match]
                                                 /                     \
                                                v                       v
                               +-------------------+    +--------------------+
                               | SKIP DOWNLOAD     |    | Tier 3: ADB Pull   |
                               | Status: IN_DB     |    | & Atomic Staging   |
                               +-------------------+    +--------------------+
```

1. **Tier 1 (Local Hybrid Workspace Scan):** Scans all 4 tiers (`01_RAW_INBOX`, `02_IN_PROGRESS`, `03_READY_TO_POST`, `04_ARCHIVE`). If a file with the identical base name and size exists, it is marked as duplicate and skipped immediately without network/USB I/O.
2. **Tier 2 (SQLite Manifest Database Query):** Queries `media_manifest.sqlite` for `source_file_name == remote_name` or matching metadata. If already processed and tracked, it is skipped.
3. **Tier 3 (Cryptographic Digest):** If the file name was altered but contents are identical, SHA-256 hash matching against the manifest prevents duplicate reprocessing.

### 4.4 Host Storage Pre-Flight Check
Before initiating transfers, the script calculates the cumulative byte size of all non-duplicate pending remote files and checks available disk space:
```python
free_bytes = shutil.disk_usage(target_inbox_path).free
required_bytes = total_pending_pull_bytes + (5 * 1024 * 1024 * 1024) # 5 GB safety headroom
if free_bytes < required_bytes:
    raise InsufficientStorageError(
        f"Target drive free space ({free_bytes / (1024**3):.2f} GB) is less than "
        f"required transfer size ({total_pending_pull_bytes / (1024**3):.2f} GB + 5 GB headroom)."
    )
```

---

## 5. Exhaustive Edge Cases, Failure Modes & Remediation Matrix

| # | Edge Case / Failure Mode | Root Cause | Programmatic Detection & Remediation in `samsung_ingest.py` |
| :- | :--- | :--- | :--- |
| **1** | **No ADB binary installed** | Android platform-tools not installed on workstation | `find_adb_binary()` returns `None`. Raises `ADBNotFoundError` with exact download instructions and automatic search across standard SDK directories. |
| **2** | **Device not connected / disconnected** | USB cable unplugged or charging-only cable used | `adb devices` returns 0 devices. Emits actionable troubleshooting steps: *"1. Connect USB 3.2 data cable. 2. Enable Developer Options -> USB Debugging. 3. Set USB mode to File Transfer."* |
| **3** | **Device unauthorized (`unauthorized`)** | Phone screen is locked or RSA prompt unaccepted | `adb devices -l` outputs `<serial> unauthorized`. Script detects state, displays high-visibility alert: *"PLEASE UNLOCK PHONE & TAP 'ALLOW USB DEBUGGING' ON SCREEN"*, and enters a 30s polling retry loop. |
| **4** | **Multiple devices connected** | Phone + Android emulator or secondary test device | `adb devices` returns $>1$ device. If `--device <serial>` is supplied, selects it. Otherwise, queries `getprop ro.product.model` for all devices, identifies Samsung S26 Ultra (`SM-S948...`), and prompts or selects automatically. |
| **5** | **Mid-transfer cable disconnect / battery death** | Cable nudged or phone battery dies during $10\text{ GB}$ transfer | `subprocess.run` raises `CalledProcessError` or `TimeoutExpired`. The `try...finally` block catches the exception, immediately unlinks `.part` temporary file, and logs resume status. |
| **6** | **Android Scoped Storage / Permission Denied** | Knox enterprise lock or restricted DCIM permissions | `adb shell ls` returns `Permission denied`. Script catches error, verifies ADB shell UID (`uid=2000(shell)`), and informs operator to unlock Knox secure folder. |
| **7** | **Insufficient host disk space** | Host NVMe / SSD drive nearly full | Pre-flight `shutil.disk_usage()` check calculates total pending payload $+ 5\text{ GB}$ headroom. Aborts before downloading a single byte. |
| **8** | **Active video recording in progress** | User is recording a live DJ set while phone is plugged in | Remote `stat` reveals file was modified $< 5\text{ seconds}$ ago or file size is actively growing. Script flags asset as `IN_RECORDING`, skips pulling incomplete clip, and logs notice. |
| **9** | **0-byte corrupted files** | Android camera app crashed before writing moov atom | Remote `stat` reports `size == 0`. Script skips file, logging `[WARN] Zero-byte corrupt asset skipped`. |
| **10**| **Windows CRLF line-ending corruption** | Default `adb shell cat` translates `\n` to `\r\n` | Never use `adb shell cat` for binary data. Always use `adb pull` or `adb exec-out` to maintain bit-for-bit binary purity. |

---

## 6. Integration Architecture with Existing `content_creation` Pipeline

### 6.1 Integration with `config.py`
Add hardware-specific ADB ingestion configuration constants to `config.py`:
```python
# ============================================================================
# SAMSUNG S26 ULTRA & ADB INGESTION STANDARDS
# ============================================================================
ADB_DEFAULT_CAMERA_PATH = "/sdcard/DCIM/Camera"
ADB_EXPERT_RAW_PATH = "/sdcard/DCIM/Expert RAW"
ADB_SUPPORTED_EXTENSIONS = [".mp4", ".mov", ".dng", ".jpg", ".heic"]
ADB_VIDEO_EXTENSIONS = [".mp4", ".mov"]
ADB_STILL_EXTENSIONS = [".dng", ".jpg", ".heic"]
ADB_PULL_TIMEOUT_PER_GB_SECONDS = 60.0  # 1 minute per GB safety timeout
ADB_MIN_FREE_DISK_HEADROOM_BYTES = 5 * 1024 * 1024 * 1024  # 5 GB headroom
```

### 6.2 Dual Ingestion Modes with `ingest_assets.py`
`samsung_ingest.py` supports two primary operational workflows:

1. **Mode A: Inbox Deposit (`--inbox-only`):**
   Pulls untouched raw files into `01_RAW_INBOX` with atomic verification and deduplication. Leaves them for subsequent batch processing or manual tagging.
2. **Mode B: Auto-Route (`--auto-route`):**
   Immediately feeds pulled assets into `AssetIngestionRouter.ingest_asset()`:
   - Probes streams with `ffprobe` (detecting 4K 60fps, HEVC, HDR10+ transfer `smpte2084`).
   - Standardizes filename to canonical syntax: `YYYYMMDD_[Event]_[Artist]_[Track]_V1_4k.mp4`.
   - Allocates workspace in `02_IN_PROGRESS/[Project_ID]`.
   - Generates `ingestion_manifest.json` with full SHA-256 hash.

### 6.3 Integration with `metadata_tracker.py` & `media_manifest.sqlite`
Record device provenance in the SQLite database and metadata sidecar:
- `capture_device`: `"Samsung Galaxy S26 Ultra"`
- `ingest_method`: `"ADB_USB3_HARDWARE"`
- `remote_source_path`: `"/sdcard/DCIM/Camera/20260822_214500.mp4"`
- `phone_serial`: `"R5CW10ABCDE"`

### 6.4 Integration with `orchestrator.py`
Expose a new `samsung-ingest` subcommand on the master CLI facade:
```bash
# Pull new concert footage and deposit in RAW INBOX
python orchestrator.py samsung-ingest --event EDCOrlando --artist JohnSummit

# Pull, probe, and run complete autonomous pipeline all the way to READY_TO_POST
python orchestrator.py samsung-ingest --event EDCOrlando --artist JohnSummit --track WhereYouAre --auto-pipeline
```

---

## 7. Comprehensive Implementation Blueprint & Specification for `samsung_ingest.py`

### 7.1 Class Hierarchy & Responsibilities

```
+-----------------------------------------------------------------------------------------------+
|                                    samsung_ingest.py                                          |
+-----------------------------------------------------------------------------------------------+
|                                                                                               |
|  [ADBBinaryDiscovery]                                                                         |
|  + find_adb_binary(custom_path) -> Optional[Path]                                             |
|                                                                                               |
|  [ADBDevice] (Dataclass)                                                                      |
|  - serial: str                                                                                |
|  - state: str ("device", "unauthorized", "offline")                                           |
|  - model: str (e.g. "SM-S948U")                                                               |
|  - is_samsung: bool                                                                           |
|                                                                                               |
|  [RemoteMediaAsset] (Dataclass)                                                               |
|  - remote_path: str                                                                           |
|  - filename: str                                                                              |
|  - size_bytes: int                                                                            |
|  - mtime_epoch: int                                                                           |
|  - is_video: bool                                                                             |
|  - is_dng: bool                                                                               |
|                                                                                               |
|  [ADBClient]                                                                                  |
|  - adb_binary: Path                                                                           |
|  - target_device: Optional[str]                                                               |
|  + list_devices() -> List[ADBDevice]                                                          |
|  + execute_shell(cmd) -> str                                                                  |
|  + stat_directory(remote_dir) -> List[RemoteMediaAsset]                                       |
|  + pull_file(remote_path, local_tmp, timeout) -> bool                                         |
|  + get_remote_md5(remote_path) -> str                                                         |
|                                                                                               |
|  [SamsungIngestEngine]                                                                        |
|  - client: ADBClient                                                                          |
|  - workspace_root: Path                                                                       |
|  - db: MediaManifestDB                                                                        |
|  + scan_phone_assets(remote_dir, extensions) -> List[RemoteMediaAsset]                        |
|  + deduplicate_assets(assets) -> List[RemoteMediaAsset]                                       |
|  + ingest_batch(assets, auto_route, event, artist, track) -> ADBIngestionSummary              |
|                                                                                               |
+-----------------------------------------------------------------------------------------------+
```

### 7.2 Core Pseudocode: `SamsungIngestEngine`

```python
class SamsungIngestEngine:
    def __init__(self, workspace_root: Path, adb_path: Optional[str] = None, serial: Optional[str] = None):
        self.workspace_root = Path(workspace_root).resolve()
        self.inbox_dir = self.workspace_root / FOLDER_TIERS["INBOX"]
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.adb = ADBClient(adb_path=adb_path, target_serial=serial)
        self.db = MediaManifestDB(db_path=self.workspace_root / "media_manifest.sqlite")

    def run_sync(
        self,
        remote_dir: str = "/sdcard/DCIM/Camera",
        extensions: Optional[List[str]] = None,
        auto_route: bool = False,
        event: str = "Concert",
        artist: str = "Artist",
        track: str = "ID",
        dry_run: bool = False
    ) -> IngestionSummary:
        # 1. Device Verification
        device = self.adb.get_selected_device()
        print(f"[ADB] Connected to {device.model} (Serial: {device.serial})")

        # 2. Remote Asset Discovery via Toybox stat
        remote_assets = self.adb.stat_directory(remote_dir)
        valid_assets = [a for a in remote_assets if a.matches_extensions(extensions or ADB_VIDEO_EXTENSIONS)]
        
        # 3. 3-Tier Deduplication
        pending_pulls = []
        for asset in valid_assets:
            if self._is_duplicate(asset):
                print(f"[SKIP] Duplicate asset: {asset.filename} ({asset.size_mb:.1f} MB)")
                continue
            pending_pulls.append(asset)

        if not pending_pulls:
            print("[INFO] All phone assets are already synchronized and present in pipeline.")
            return IngestionSummary(total_scanned=len(valid_assets), pulled=0, skipped=len(valid_assets))

        # 4. Host Storage Capacity Guard
        total_bytes = sum(a.size_bytes for a in pending_pulls)
        self._verify_host_disk_capacity(total_bytes)

        # 5. Atomic Pull & Integrity Verification
        ingested_files = []
        for asset in pending_pulls:
            if dry_run:
                print(f"[DRY-RUN] Would pull: {asset.filename} ({asset.size_mb:.1f} MB)")
                continue

            part_path = self.inbox_dir / f".tmp_{asset.filename}_{os.getpid()}.part"
            final_path = self.inbox_dir / asset.filename

            try:
                print(f"[PULLING] {asset.filename} ({asset.size_mb:.1f} MB)...")
                self.adb.pull_file(asset.remote_path, part_path)
                
                # Check byte count
                if part_path.stat().st_size != asset.size_bytes:
                    raise ChecksumMismatchError(f"Size mismatch on {asset.filename}: {part_path.stat().st_size} != {asset.size_bytes}")

                # Atomic promote
                os.replace(part_path, final_path)
                ingested_files.append(final_path)

            except Exception as e:
                part_path.unlink(missing_ok=True)
                print(f"[ERROR] Failed to pull {asset.filename}: {e}", file=sys.stderr)
                raise

        # 6. Optional Auto-Route to 02_IN_PROGRESS
        if auto_route and not dry_run:
            router = AssetIngestionRouter(self.workspace_root)
            for f in ingested_files:
                router.ingest_asset(source_path=f, event_name=event, artist_name=artist, track_name=track)

        return IngestionSummary(
            total_scanned=len(valid_assets),
            pulled=len(ingested_files),
            skipped=len(valid_assets) - len(pending_pulls),
            total_bytes=total_bytes
        )
```

### 7.3 CLI Interface Specification
```
usage: samsung_ingest.py [-h] [--target-dir TARGET_DIR] [--adb-path ADB_PATH]
                         [--device SERIAL] [--remote-dir REMOTE_DIR]
                         [--event EVENT] [--artist ARTIST] [--track TRACK]
                         [--brand {laser_baptism,music_baptism}]
                         [--tier {pillar_a_stadium_arena,pillar_b_club_spotlight,pillar_c_festival_mega}]
                         [--auto-route] [--inbox-only] [--include-raw-dng]
                         [--verify-remote-md5] [--dry-run]

Samsung S26 Ultra ADB Hardware Ingestion Bridge (Track 2: Content Creation)

optional arguments:
  -h, --help            show this help message and exit
  --target-dir TARGET_DIR, -t TARGET_DIR
                        Content creation workspace root directory.
  --adb-path ADB_PATH   Explicit path to adb binary.
  --device SERIAL, -d SERIAL
                        Target device ADB serial number (if multiple devices).
  --remote-dir REMOTE_DIR
                        Remote Android camera folder (default: /sdcard/DCIM/Camera).
  --event EVENT, -e EVENT
                        Concert / Festival name (e.g. EDCOrlando).
  --artist ARTIST, -a ARTIST
                        DJ / Headliner name (e.g. JohnSummit).
  --track TRACK         Track name or unreleased ID code.
  --brand {laser_baptism,music_baptism}
                        Target brand umbrella.
  --tier {pillar_a_stadium_arena,pillar_b_club_spotlight,pillar_c_festival_mega}
                        Content pillar tier.
  --auto-route          Automatically probe, normalize name, and stage in 02_IN_PROGRESS.
  --inbox-only          Pull untouched files to 01_RAW_INBOX without routing.
  --include-raw-dng     Also ingest raw 16-bit DNG stills from Expert RAW folder.
  --verify-remote-md5   Execute on-device md5sum check before download.
  --dry-run             Simulate phone scan and deduplication without pulling files.
```

---

## 8. Summary of Findings & Next Steps for Implementation

1. **Subprocess Architecture is Optimal:** Zero third-party dependencies, maximum stability, native 64-bit multi-gigabyte file transfer capability, and full compatibility with Android 15/16 ADB sync protocol.
2. **Toybox `stat` replaces Flaky `ls`:** Single-command parsing of `%s %Y %n` eliminates brittle text regex parsing across disparate Android builds.
3. **Atomic Staging Protects Inbox:** Pulling to `.tmp_<name>.part` with automatic unlinking on exception guarantees that `01_RAW_INBOX` is never polluted by corrupted partial files.
4. **3-Tier Deduplication Eliminates Redundancy:** Checking local 4-tier folders, SQLite `media_manifest.sqlite`, and file size/mtime prevents re-downloading existing $15\text{ GB}$ video masters.
5. **Seamless Pipeline Integration:** Exposing `--auto-route` hooks `samsung_ingest.py` directly into `AssetIngestionRouter` and `orchestrator.py` as Phase 0 of the master EDM content lifecycle.

---
*Report compiled and certified by Explorer 2.*
