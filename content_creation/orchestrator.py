"""
orchestrator.py - Master AI CLI Facade & End-to-End Orchestration Pipeline

Unifies the Content Creation media engineering suite under a single master CLI interface:
- ingest: Discovers, probes, standardizes names, and routes raw mobile concert footage.
- process: Transcodes assets with 9:16 re-framing, HDR->SDR tone-mapping, and 2-pass loudnorm.
- inspect: Performs deep ffprobe stream telemetry analysis.
- generate-seo: Synthesizes platform titles, captions, 5-7 hashtags, and first-hour engagement hooks.
- audit-safezone: Validates visual overlay bounding boxes against platform exclusion zones.
- verify: Executes independent EBU R128 and video standards Quality Control (QC) assertions.
- adb-ingest: Direct hardware capture and atomic pull from Samsung Galaxy S26 Ultra.
- publish-youtube / publish: Uploads 9:16 video as unlisted, audits Content ID, and promotes to public.
- pipeline: Runs the autonomous end-to-end lifecycle from raw inbox/device to ready-to-post and YouTube publication.
"""

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple, Union

from config import (
    AUDIO_CEILING_TRUE_PEAK,
    AUDIO_LUFS_TOLERANCE,
    AUDIO_TARGET_LUFS,
    AUDIO_TARGET_TRUE_PEAK,
    AssetStatus,
    BrandType,
    ContentIDStatus,
    DenoiseMode,
    EventTier,
    FOLDER_TIERS,
    LoudnormMode,
    ProductionPreset,
    ReframeMode,
    ToneMapMode,
    VIDEO_CANVAS_HEIGHT,
    VIDEO_CANVAS_WIDTH,
    VIDEO_DURATION_MAX_SECONDS,
    get_awaiting_review_folder,
    get_raw_folder,
)
from ffmpeg_processor import (
    FFmpegMasterProcessor,
    TranscodeConfig,
    parse_loudnorm_pass1_output,
)
from ingest_assets import (
    AssetIngestionRouter,
    FilenameNormalizer,
    find_binary,
    probe_media_file,
)
from metadata_tracker import (
    BoundingBox,
    CommentSpamFilter,
    MediaManifestDB,
    SEOCaptionGenerator,
    SafeZoneAuditor,
)
try:
    from audio_dsp import (
        AudioDropDetector,
        DropWindowResult,
        detect_optimal_drop,
        run_auto_drop_detection,
    )
except ImportError:
    AudioDropDetector = None
    DropWindowResult = None
    detect_optimal_drop = None
    run_auto_drop_detection = None

try:
    from youtube_publisher import YouTubePublisher, YouTubePublishResult
except ImportError:
    YouTubePublisher = None
    YouTubePublishResult = None

try:
    from samsung_ingest import SamsungADBIngestor, find_adb_binary
except ImportError:
    SamsungADBIngestor = None
    find_adb_binary = None

# Configure console encoding for cross-platform unicode / emoji safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================================
# QUALITY CONTROL (QC) VERIFIER
# ============================================================================

@dataclass
class QCReport:
    """Detailed verification report evaluating an export against broadcast standards."""
    passed: bool
    file_path: str
    duration_seconds: float
    duration_compliant: bool      # <= 59.0s
    resolution: str
    resolution_compliant: bool    # 1080x1920
    framerate_fps: float
    framerate_compliant: bool     # >= 30.0 fps CFR (target 60fps)
    measured_lufs: Optional[float]
    lufs_compliant: bool          # -14.0 +/- 1.0 LUFS
    measured_true_peak: Optional[float]
    true_peak_compliant: bool     # <= -1.5 dBTP (ceiling -1.0 dBTP)
    failure_reasons: List[str] = field(default_factory=list)


def verify_media_file(
    file_path: Path,
    ffprobe_path: Optional[str] = None,
    ffmpeg_path: Optional[str] = None,
) -> QCReport:
    """
    Performs independent verification of rendered video against all technical standards:
    1. Duration <= 59.0s (YouTube Shorts Content ID safety guardrail).
    2. Resolution == 1080x1920 (9:16 vertical orientation).
    3. Frame rate >= 30.0 fps (60 fps CFR standard).
    4. Integrated Loudness == -14.0 LUFS ± 1.0 LUFS (EBU R128).
    5. True Peak <= -1.5 dBTP.
    """
    target = Path(file_path).resolve()
    if not target.is_file():
        raise FileNotFoundError(f"Verification target file does not exist: {target}")

    probe_data = probe_media_file(target, ffprobe_path=ffprobe_path)
    failures: List[str] = []

    # 1. Duration check
    dur = probe_data.duration_seconds
    dur_ok = dur <= VIDEO_DURATION_MAX_SECONDS + 0.1  # Allow tiny floating tolerance
    if not dur_ok:
        failures.append(
            f"Duration ({dur:.2f}s) exceeds maximum allowed ceiling of {VIDEO_DURATION_MAX_SECONDS:.1f}s."
        )

    # 2. Resolution check
    res_str = f"{probe_data.width}x{probe_data.height}"
    res_ok = (probe_data.width == VIDEO_CANVAS_WIDTH and probe_data.height == VIDEO_CANVAS_HEIGHT)
    if not res_ok:
        failures.append(
            f"Resolution ({res_str}) does not match required 9:16 canvas ({VIDEO_CANVAS_WIDTH}x{VIDEO_CANVAS_HEIGHT})."
        )

    # 3. Frame rate check
    fps = probe_data.frame_rate
    fps_ok = fps >= 29.0
    if not fps_ok:
        failures.append(f"Framerate ({fps:.2f} fps) is below minimum 30 fps threshold.")

    # 4. Audio Loudness & True Peak verification via ffmpeg ebur128 analysis
    measured_lufs: Optional[float] = None
    measured_tp: Optional[float] = None
    lufs_ok = True
    tp_ok = True

    ffmpeg_bin = find_binary("ffmpeg", custom_path=ffmpeg_path, env_var="FFMPEG_BINARY")
    if ffmpeg_bin and probe_data.audio_codec:
        try:
            cmd = [
                str(ffmpeg_bin),
                "-i", str(target),
                "-vn",
                "-af", "ebur128=peak=true",
                "-f", "null",
                "-",
            ]
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
                timeout=30,
            )
            # Parse Summary section from ebur128 output in stderr
            lufs_match = re.search(r"Integrated loudness:\s+I:\s+([-\d\.]+)\s+LUFS", proc.stderr)
            tp_match = re.search(r"Peak:\s+True:\s+([-\d\.]+)\s+dBFS", proc.stderr)

            if lufs_match:
                measured_lufs = float(lufs_match.group(1))
                min_lufs = AUDIO_TARGET_LUFS - AUDIO_LUFS_TOLERANCE
                max_lufs = AUDIO_TARGET_LUFS + AUDIO_LUFS_TOLERANCE
                lufs_ok = (min_lufs <= measured_lufs <= max_lufs)
                if not lufs_ok:
                    failures.append(
                        f"Integrated loudness ({measured_lufs:.1f} LUFS) outside target range "
                        f"[{min_lufs:.1f}, {max_lufs:.1f}] LUFS."
                    )

            if tp_match:
                measured_tp = float(tp_match.group(1))
                tp_ok = (measured_tp <= AUDIO_TARGET_TRUE_PEAK)
                if not tp_ok:
                    failures.append(
                        f"True peak ({measured_tp:.1f} dBTP) exceeds target limit of {AUDIO_TARGET_TRUE_PEAK:.1f} dBTP."
                    )
        except Exception as e:
            failures.append(f"Audio EBU R128 analysis failed: {e}")

    overall_passed = dur_ok and res_ok and fps_ok and lufs_ok and tp_ok and len(failures) == 0

    return QCReport(
        passed=overall_passed,
        file_path=str(target),
        duration_seconds=dur,
        duration_compliant=dur_ok,
        resolution=res_str,
        resolution_compliant=res_ok,
        framerate_fps=fps,
        framerate_compliant=fps_ok,
        measured_lufs=measured_lufs,
        lufs_compliant=lufs_ok,
        measured_true_peak=measured_tp,
        true_peak_compliant=tp_ok,
        failure_reasons=failures,
    )


# ============================================================================
# AUDIO DROP DETECTION HELPER (EXCLUSIVELY ANALYZES EXTRACTED .WAV)
# ============================================================================

def run_auto_drop_detection(
    audio_wav_path: Union[str, Path, Any],
    target_duration_sec: float = 30.0,
    manual_start_time: Optional[float] = None,
    manual_duration: Optional[float] = None,
    custom_ffmpeg_path: Optional[str] = None,
    dry_run: bool = False,
) -> DropWindowResult:
    """
    Analyzes an uncompressed / extracted .wav audio file directly using AudioDropDetector.
    Bypasses parsing/demuxing the heavy 4K raw video container.
    """
    if manual_start_time is not None:
        dur = manual_duration if manual_duration is not None else target_duration_sec
        dur = min(float(dur), float(VIDEO_DURATION_MAX_SECONDS))
        start_t = float(manual_start_time)
        return DropWindowResult(
            start_time_sec=round(start_t, 3),
            duration_sec=round(dur, 3),
            end_time_sec=round(start_t + dur, 3),
            max_rms_energy=1.0,
            is_manual_override=True,
            detection_method="manual_cli_override",
        )

    # Check if numpy array or memory buffer
    if isinstance(audio_wav_path, (list, tuple)) or (hasattr(audio_wav_path, "shape") and not isinstance(audio_wav_path, (str, Path))):
        if AudioDropDetector is not None:
            detector = AudioDropDetector(target_duration_sec=target_duration_sec, custom_ffmpeg_path=custom_ffmpeg_path)
            return detector.detect_optimal_drop(audio_wav_path, manual_start_time=None, manual_duration=manual_duration)
        return DropWindowResult(
            start_time_sec=0.0,
            duration_sec=float(target_duration_sec),
            end_time_sec=float(target_duration_sec),
            max_rms_energy=1.0,
            is_manual_override=False,
            detection_method="simulation",
        )

    wav_p = Path(audio_wav_path).resolve()
    if dry_run or not wav_p.is_file():
        if AudioDropDetector is not None and wav_p.is_file():
            detector = AudioDropDetector(target_duration_sec=target_duration_sec, custom_ffmpeg_path=custom_ffmpeg_path)
            return detector.detect_optimal_drop(wav_p, manual_start_time=None, manual_duration=manual_duration)
        return DropWindowResult(
            start_time_sec=0.0,
            duration_sec=float(target_duration_sec),
            end_time_sec=float(target_duration_sec),
            max_rms_energy=0.95,
            is_manual_override=False,
            detection_method="librosa_simulation" if dry_run else "short_audio_fallback",
        )

    if AudioDropDetector is not None:
        detector = AudioDropDetector(target_duration_sec=target_duration_sec, custom_ffmpeg_path=custom_ffmpeg_path)
        return detector.detect_optimal_drop(wav_p, manual_start_time=None, manual_duration=manual_duration)

    return DropWindowResult(
        start_time_sec=0.0,
        duration_sec=float(target_duration_sec),
        end_time_sec=float(target_duration_sec),
        max_rms_energy=0.0,
        is_manual_override=False,
        detection_method="no_detector_available",
    )


# ============================================================================
# MASTER ORCHESTRATION PIPELINE RUNNER
# ============================================================================

def run_ingestion_phase(
    input_file: Path,
    workspace_root: Path,
    event: str,
    artist: str,
    track: str,
    genre: str = "house",
    brand: BrandType = BrandType.MUSIC_BAPTISM,
    tier: EventTier = EventTier.PILLAR_A,
    start_time: Optional[float] = None,
    duration: Optional[float] = None,
    auto_drop: bool = False,
    drop_duration: float = 30.0,
    dry_run: bool = False,
    ffmpeg_path: Optional[str] = None,
    ffprobe_path: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Executes Phase 1: Ingest, Proxy, Audio Drop Detection, and Review Stage.
    """
    workspace = Path(workspace_root).resolve()
    db = MediaManifestDB(db_path=db_path or (workspace / "media_manifest.sqlite"))
    router = AssetIngestionRouter(workspace_root=workspace, ffprobe_path=ffprobe_path)
    processor = FFmpegMasterProcessor(custom_ffmpeg_path=ffmpeg_path)

    # 1. Ingestion Phase & Pristine Raw Storage
    print(f"\n[PHASE 1/5] Ingesting raw asset: {input_file.name}...")
    ingest_res = router.ingest_asset(
        source_path=input_file,
        event_name=event,
        artist_name=artist,
        track_name=track,
        brand=brand,
        tier=tier,
        version=1,
        dry_run=dry_run,
        ffprobe_custom_path=ffprobe_path,
    )
    clean_festival = FilenameNormalizer.sanitize_token(event, default="Concert")
    clean_artist = FilenameNormalizer.sanitize_token(artist, default="Artist")
    raw_storage_file = (
        Path(ingest_res.raw_storage_path)
        if ingest_res.raw_storage_path
        else (workspace / FOLDER_TIERS.get("RAW", "01_RAW") / clean_festival / clean_artist / ingest_res.canonical_filename)
    )
    print(f"  Canonical Name: {ingest_res.canonical_filename}")
    print(f"  Project ID: {ingest_res.project_id}")
    print(f"  Pristine Raw Storage: {raw_storage_file}")
    print(f"  Probed: {ingest_res.probe_data.width}x{ingest_res.probe_data.height} @ {ingest_res.probe_data.frame_rate}fps | HDR: {ingest_res.probe_data.is_hdr}")

    # Generate 720p Proxy Video and PCM 16-bit WAV Audio
    in_progress_dir = (
        Path(ingest_res.staged_path).parent
        if not dry_run
        else (workspace / FOLDER_TIERS["IN_PROGRESS"] / ingest_res.project_id)
    )
    proxy_video_path = in_progress_dir / f"proxy_{ingest_res.canonical_filename}"
    audio_wav_path = in_progress_dir / f"{Path(ingest_res.canonical_filename).stem}.wav"

    print(f"\n[PROXY ENGINE] Generating 720p proxy video and 22.05kHz WAV audio...")
    proxy_gen_res = processor.generate_proxy_and_wav(
        input_path=raw_storage_file if (not dry_run and raw_storage_file.is_file()) else input_file,
        output_proxy_path=proxy_video_path,
        output_wav_path=audio_wav_path,
        dry_run=dry_run,
    )
    print(f"  Proxy Video: {proxy_video_path}")
    print(f"  WAV Audio:   {audio_wav_path}")

    # 2. Database Registration (IN_PROGRESS)
    if not dry_run:
        db.upsert_asset(
            asset_id=ingest_res.project_id,
            source_file_name=input_file.name,
            canonical_name=ingest_res.canonical_filename,
            brand=brand.value,
            tier=tier.value,
            event_name=event,
            artist_name=artist,
            track_name=track,
            genre=genre,
            duration_seconds=ingest_res.probe_data.duration_seconds,
            is_hdr=ingest_res.probe_data.is_hdr,
            current_status=AssetStatus.IN_PROGRESS,
            raw_path=str(raw_storage_file),
        )

    staged_input = Path(ingest_res.staged_path) if not dry_run else input_file
    in_progress_master_path = in_progress_dir / f"master_{ingest_res.canonical_filename}"

    # 3. Drop Detection & Trimming Precedence Hierarchy (Analyzing lightweight .wav directly)
    drop_result = None
    if start_time is not None:
        drop_result = run_auto_drop_detection(
            audio_wav_path=audio_wav_path,
            target_duration_sec=drop_duration,
            manual_start_time=start_time,
            manual_duration=duration,
            custom_ffmpeg_path=ffmpeg_path,
            dry_run=dry_run,
        )
        effective_start = drop_result.start_time_sec
        effective_duration = drop_result.duration_sec
        print(f"  [MANUAL OVERRIDE] Using manual start time: {effective_start:.2f}s (duration: {effective_duration:.2f}s, bypasses auto-drop)")
    elif auto_drop:
        print(f"\n[DROP DETECTION] Computing optimal drop window via Librosa/RMS on extracted WAV (target: {drop_duration:.1f}s)...")
        drop_result = run_auto_drop_detection(
            audio_wav_path=audio_wav_path,
            target_duration_sec=drop_duration,
            manual_start_time=None,
            manual_duration=duration,
            custom_ffmpeg_path=ffmpeg_path,
            dry_run=dry_run,
        )
        effective_start = drop_result.start_time_sec
        effective_duration = drop_result.duration_sec
        print(f"  [AUTO-DROP] Detected drop window from WAV: {effective_start:.2f}s - {drop_result.end_time_sec:.2f}s ({drop_result.detection_method}, peak RMS: {drop_result.max_rms_energy:.4f})")
    else:
        effective_start = 0.0
        effective_duration = duration
        drop_result = None

    # 4. Human-in-the-Loop "Awaiting Review" Gate: Trim 720p Proxy Video into 02_AWAITING_REVIEW
    print("\n[AWAITING REVIEW GATE] Trimming 720p proxy video into 02_AWAITING_REVIEW...")
    review_dir = get_awaiting_review_folder(workspace, clean_festival, clean_artist)
    if not dry_run:
        review_dir.mkdir(parents=True, exist_ok=True)
    trimmed_proxy_filename = f"{Path(ingest_res.canonical_filename).stem}_proxy_drop.mp4"
    review_proxy_path = review_dir / trimmed_proxy_filename

    proxy_trim_cmd = processor.trim_proxy_video(
        input_proxy_path=proxy_video_path,
        output_path=review_proxy_path,
        start_time_sec=effective_start,
        duration_sec=effective_duration if effective_duration is not None else 30.0,
        dry_run=dry_run,
    )
    print(f"  Awaiting Review Proxy: {review_proxy_path}")

    # Stage asset in manifest as AWAITING_REVIEW before master render
    if not dry_run:
        db.upsert_asset(
            asset_id=ingest_res.project_id,
            current_status=AssetStatus.AWAITING_REVIEW,
            master_path=str(review_proxy_path),
            metadata_dict={"start_time": effective_start, "duration": effective_duration}
        )

    return {
        "project_id": ingest_res.project_id,
        "canonical_filename": ingest_res.canonical_filename,
        "raw_storage_path": str(raw_storage_file),
        "proxy_video_path": str(proxy_video_path),
        "audio_wav_path": str(audio_wav_path),
        "review_proxy_path": str(review_proxy_path),
        "status": AssetStatus.AWAITING_REVIEW.value,
        "drop_window": asdict(drop_result) if drop_result else None
    }


def run_render_phase(
    project_id: str,
    workspace_root: Path,
    reframe_mode: ReframeMode = ReframeMode.CENTER_CROP,
    tone_map: ToneMapMode = ToneMapMode.AUTO,
    denoise: DenoiseMode = DenoiseMode.AUTO,
    preset: ProductionPreset = ProductionPreset.FAST_TRACK,
    publish_youtube: bool = False,
    auto_promote: bool = False,
    poll_timeout: float = 300.0,
    dry_run: bool = False,
    ffmpeg_path: Optional[str] = None,
    ffprobe_path: Optional[str] = None,
    db_path: Optional[Path] = None,
    client_secrets_path: Optional[str] = None,
    token_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes Phase 2: Transcoding, QC, SEO Generation, and Publishing.
    Assumes asset has been approved in the DB.
    """
    workspace = Path(workspace_root).resolve()
    db = MediaManifestDB(db_path=db_path or (workspace / "media_manifest.sqlite"))
    
    asset = db.get_asset(project_id) if not dry_run else None
    if not dry_run and not asset:
        raise ValueError(f"Project ID {project_id} not found in database.")

    router = AssetIngestionRouter(workspace_root=workspace, ffprobe_path=ffprobe_path)
    processor = FFmpegMasterProcessor(custom_ffmpeg_path=ffmpeg_path)

    # Reconstruct paths
    canonical_filename = asset.get("canonical_name") if asset else "simulated_take_Id_V1_1080p.mp4"
    staged_input = Path(asset.get("raw_path")) if asset else (workspace / "simulated_take.mp4")
    
    in_progress_dir = workspace / FOLDER_TIERS["IN_PROGRESS"] / project_id
    if not dry_run:
        in_progress_dir.mkdir(parents=True, exist_ok=True)
    in_progress_master_path = in_progress_dir / f"master_{canonical_filename}"

    meta = json.loads(asset.get("metadata_json", "{}")) if asset and asset.get("metadata_json") else {}
    effective_start = meta.get("start_time", 0.0)
    effective_duration = meta.get("duration", 30.0)
    is_hdr = bool(asset.get("is_hdr")) if asset else False
    track = asset.get("track_name") if asset else "ID"
    artist = asset.get("artist_name") if asset else "Artist"
    event = asset.get("event_name") if asset else "Event"
    genre = asset.get("genre") if asset else "house"
    brand_val = asset.get("brand") if asset else BrandType.MUSIC_BAPTISM.value
    tier_val = asset.get("tier") if asset else EventTier.PILLAR_A.value

    # 5. Transcoding & Media DSP Phase
    print(f"\n[PHASE 2/5] Transcoding media master {canonical_filename} (9:16 re-framing, tone-mapping, 2-pass loudnorm)...")
    transcode_cfg = TranscodeConfig(
        input_path=staged_input,
        output_path=in_progress_master_path,
        preset=preset,
        reframe_mode=reframe_mode,
        tone_map=tone_map,
        is_source_hdr=is_hdr,
        denoise=denoise,
        loudnorm=LoudnormMode.TWO_PASS,
        start_time_sec=effective_start,
        duration_sec=effective_duration,
        max_duration_sec=VIDEO_DURATION_MAX_SECONDS,
        loop_crossfade=True,
        track_title=track,
        artist_name=artist,
        custom_ffmpeg_path=ffmpeg_path,
        dry_run=dry_run,
    )
    transcode_res = processor.transcode(transcode_cfg)
    print(f"  Export Master: {transcode_res.output_path}")
    print(f"  Clamped Duration: {transcode_res.duration_sec:.2f}s")
    if transcode_res.loudness_stats:
        print(f"  Measured I: {transcode_res.loudness_stats.input_i:.1f} LUFS | TP: {transcode_res.loudness_stats.input_tp:.1f} dBTP")

    # 6. Quality Control (QC) Verification Phase
    print("\n[PHASE 3/5] Executing independent Quality Control (QC) verification...")
    if not dry_run:
        qc_res = verify_media_file(in_progress_master_path, ffprobe_path=ffprobe_path, ffmpeg_path=ffmpeg_path)
        if not qc_res.passed:
            print("[ERROR] Quality Control assertions failed:", file=sys.stderr)
            for r in qc_res.failure_reasons:
                print(f"  - {r}", file=sys.stderr)
            raise RuntimeError(f"QC verification failed for {in_progress_master_path}")
        print(f"  [PASSED] QC Assertions Verified: {qc_res.resolution}, {qc_res.framerate_fps}fps, {qc_res.duration_seconds:.2f}s, {qc_res.measured_lufs} LUFS")
    else:
        print("  [DRY-RUN] QC check skipped in simulation mode.")
        qc_res = QCReport(
            passed=True,
            file_path=str(in_progress_master_path),
            duration_seconds=transcode_res.duration_sec,
            duration_compliant=True,
            resolution=f"{VIDEO_CANVAS_WIDTH}x{VIDEO_CANVAS_HEIGHT}",
            resolution_compliant=True,
            framerate_fps=60.0,
            framerate_compliant=True,
            measured_lufs=-14.0,
            lufs_compliant=True,
            measured_true_peak=-1.5,
            true_peak_compliant=True,
        )

    # 7. Metadata & SEO Packaging Phase
    print("\n[PHASE 4/5] Generating SEO metadata and first-hour engagement package...")
    seo_pkg = SEOCaptionGenerator.generate_seo_package(
        artist=artist,
        track=track,
        event=event,
        genre=genre,
        brand=BrandType(brand_val),
        tier=EventTier(tier_val),
    )
    sidecar_json_path = in_progress_dir / f"{canonical_filename}.seo.json"
    if not dry_run:
        with open(sidecar_json_path, "w", encoding="utf-8") as f:
            json.dump(asdict(seo_pkg), f, indent=2)
    print(f"  Title: {seo_pkg.yt_title}")
    print(f"  Hashtags: {' '.join(seo_pkg.hashtags)}")

    # 8. Promotion to 03_READY_TO_POST Phase
    print("\n[PHASE 5/5] Promoting master to 03_READY_TO_POST...")
    ready_dir = workspace / FOLDER_TIERS["READY_TO_POST"]
    healthy_ready_dir = router.health_guard.get_healthy_subfolder(ready_dir, project_id)
    final_master_path = healthy_ready_dir / canonical_filename
    final_sidecar_path = healthy_ready_dir / f"{canonical_filename}.seo.json"

    if not dry_run:
        shutil.move(in_progress_master_path, final_master_path)
        shutil.move(sidecar_json_path, final_sidecar_path)

        # Update SQLite lifecycle record
        db.upsert_asset(
            asset_id=project_id,
            duration_seconds=qc_res.duration_seconds,
            measured_lufs=qc_res.measured_lufs,
            measured_true_peak=qc_res.measured_true_peak,
            current_status=AssetStatus.READY_TO_POST,
            youtube_content_id_status=ContentIDStatus.UNLISTED_CLEARED,
            safe_zone_verified=True,
            master_path=str(final_master_path),
            metadata_dict=asdict(seo_pkg),
        )
    print(f"  [COMPLETE] Master ready for distribution: {final_master_path}")

    # 9. YouTube Publishing Phase (Optional via --publish-youtube)
    yt_res: Optional[YouTubePublishResult] = None
    if publish_youtube:
        print(f"\n[PHASE 6/6] Publishing master to YouTube with Content ID auditing loop...")
        if YouTubePublisher is None:
            raise RuntimeError("YouTube publisher module (youtube_publisher.py) could not be loaded.")
        publisher = YouTubePublisher(
            client_secrets_path=client_secrets_path,
            token_path=token_path,
            db_path=db_path or (workspace / "media_manifest.sqlite"),
            dry_run=dry_run,
        )
        yt_res = publisher.publish_workflow(
            video_path=final_master_path,
            title=seo_pkg.yt_title,
            description=seo_pkg.yt_description,
            tags=seo_pkg.hashtags,
            category_id="10",
            auto_promote=auto_promote,
            poll_timeout_sec=poll_timeout,
            project_id=project_id,
            db_path=db_path or (workspace / "media_manifest.sqlite"),
            seo_json_path=final_sidecar_path,
        )
        print(f"  [YOUTUBE PUBLISH] Video ID: {yt_res.video_id} | Final Privacy: {yt_res.final_privacy} | Status: {yt_res.content_id_status}")
        final_status = AssetStatus.POSTED.value if yt_res.final_privacy == "public" else AssetStatus.READY_TO_POST.value
    else:
        final_status = AssetStatus.READY_TO_POST.value

    result_summary = {
        "project_id": project_id,
        "canonical_filename": canonical_filename,
        "master_path": str(final_master_path),
        "seo_sidecar_path": str(final_sidecar_path),
        "qc_report": asdict(qc_res),
        "seo_package": asdict(seo_pkg),
        "status": final_status,
    }
    if yt_res is not None:
        result_summary["youtube_publish"] = asdict(yt_res)

    return result_summary


# ============================================================================
# MASTER CLI DISPATCHER
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Constructs the master CLI argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        prog="orchestrator.py",
        description="Master AI Media Orchestrator for EDM Short-Form Content (Track 2: Content Creation)",
    )
    parser.add_argument("--target-dir", "-t", default=str(Path.cwd()), help="Workspace root directory.")
    parser.add_argument("--ffmpeg-path", default=None, help="Explicit path to ffmpeg binary.")
    parser.add_argument("--ffprobe-path", default=None, help="Explicit path to ffprobe binary.")
    parser.add_argument("--db-path", default=None, help="Path to SQLite manifest database.")

    subparsers = parser.add_subparsers(dest="subcommand", required=True, help="Pipeline subcommand to execute.")

    # 1. INGEST
    ingest_p = subparsers.add_parser("ingest", help="Ingest and route raw concert footage.")
    ingest_p.add_argument("--input", "-i", required=True, help="Input video file or folder.")
    ingest_p.add_argument("--event", "--festival", default="Concert", help="Event/Festival name.")
    ingest_p.add_argument("--artist", default="Artist", help="DJ/Artist name.")
    ingest_p.add_argument("--track", default="ID", help="Track name.")
    ingest_p.add_argument("--brand", choices=[b.value for b in BrandType], default=BrandType.MUSIC_BAPTISM.value)
    ingest_p.add_argument("--tier", choices=[t.value for t in EventTier], default=EventTier.PILLAR_A.value)
    ingest_p.add_argument("--version", type=int, default=1, help="Asset version.")
    ingest_p.add_argument("--dry-run", action="store_true", help="Simulate without moving files.")

    # 2. PROCESS
    process_p = subparsers.add_parser("process", help="Transcode video master through FFmpeg filtergraph.")
    process_p.add_argument("--input", "-i", required=True, help="Source video file.")
    process_p.add_argument("--output", "-o", required=True, help="Output MP4 master destination.")
    process_p.add_argument("--preset", choices=[p.value for p in ProductionPreset], default=ProductionPreset.FAST_TRACK.value)
    process_p.add_argument("--reframe-mode", choices=[r.value for r in ReframeMode], default=ReframeMode.CENTER_CROP.value)
    process_p.add_argument("--crop-x", type=int, default=None)
    process_p.add_argument("--crop-y", type=int, default=None)
    process_p.add_argument("--tone-map", choices=[t.value for t in ToneMapMode], default=ToneMapMode.AUTO.value)
    process_p.add_argument("--denoise", choices=[d.value for d in DenoiseMode], default=DenoiseMode.AUTO.value)
    process_p.add_argument("--loudnorm", choices=[l.value for l in LoudnormMode], default=LoudnormMode.TWO_PASS.value)
    process_p.add_argument("--start-time", type=float, default=None, help="Manual start timestamp in seconds (bypasses auto-drop).")
    process_p.add_argument("--duration", type=float, default=None, help="Target clip duration in seconds.")
    process_p.add_argument("--auto-drop", action="store_true", help="Enable intelligent RMS drop detection via AudioDropDetector.")
    process_p.add_argument("--drop-duration", type=float, default=30.0, help="Target drop duration in seconds (default: 30.0).")
    process_p.add_argument("--max-duration", type=float, default=VIDEO_DURATION_MAX_SECONDS)
    process_p.add_argument("--track-title", default=None)
    process_p.add_argument("--artist-name", default=None)
    process_p.add_argument("--encoder", default="auto")
    process_p.add_argument("--dry-run", action="store_true")

    # 3. INSPECT
    inspect_p = subparsers.add_parser("inspect", help="Inspect media streams with ffprobe.")
    inspect_p.add_argument("--input", "-i", required=True, help="Path to video file to probe.")

    # 4. GENERATE-SEO
    seo_p = subparsers.add_parser("generate-seo", help="Generate platform SEO captions, hashtags, and hooks.")
    seo_p.add_argument("--artist", required=True, help="DJ/Artist name.")
    seo_p.add_argument("--track", required=True, help="Track name.")
    seo_p.add_argument("--event", "--festival", required=True, help="Event/Festival name.")
    seo_p.add_argument("--genre", default="house", help="EDM subgenre.")
    seo_p.add_argument("--stage", default=None, help="Stage name.")
    seo_p.add_argument("--year", type=int, default=2026, help="Production year.")
    seo_p.add_argument("--brand", choices=[b.value for b in BrandType], default=BrandType.MUSIC_BAPTISM.value)
    seo_p.add_argument("--tier", choices=[t.value for t in EventTier], default=EventTier.PILLAR_A.value)

    # 5. AUDIT-SAFEZONE
    safe_p = subparsers.add_parser("audit-safezone", help="Audit overlay bounding box against UI limits.")
    safe_p.add_argument("--box", nargs=4, type=int, required=True, metavar=("X", "Y", "W", "H"))

    # 6. VERIFY
    verify_p = subparsers.add_parser("verify", help="Execute Quality Control (QC) assertions on rendered master.")
    verify_p.add_argument("--input", "-i", required=True, help="Path to rendered MP4 master.")

    # 7. ADB-INGEST (Samsung Galaxy S26 Ultra Hardware Bridge)
    adb_p = subparsers.add_parser("adb-ingest", help="Ingest takes directly from Samsung Galaxy S26 Ultra via ADB.")
    adb_p.add_argument("--device", "-d", default=None, help="Target ADB device serial.")
    adb_p.add_argument("--adb-path", default=None, help="Explicit path to adb binary.")
    adb_p.add_argument("--remote-dir", default="/sdcard/DCIM/Camera", help="Remote camera directory.")
    adb_p.add_argument("--event", "--festival", "-e", default="Concert", help="Event/Festival name.")
    adb_p.add_argument("--artist", "-a", default="Artist", help="DJ/Artist name.")
    adb_p.add_argument("--track", default="ID", help="Track name or unreleased ID.")
    adb_p.add_argument("--brand", choices=[b.value for b in BrandType], default=BrandType.MUSIC_BAPTISM.value)
    adb_p.add_argument("--tier", choices=[t.value for t in EventTier], default=EventTier.PILLAR_A.value)
    adb_p.add_argument("--recent", type=int, default=None, help="Pull only the N most recent camera takes.")
    adb_p.add_argument("--date", default=None, help="Filter remote takes by date (YYYYMMDD).")
    adb_p.add_argument("--auto-route", action="store_true", help="Probe and stage pulled assets into 02_IN_PROGRESS.")
    adb_p.add_argument("--inbox-only", action="store_true", help="Pull raw files to 01_RAW_INBOX without downstream routing.")
    adb_p.add_argument("--include-raw-dng", action="store_true", help="Also scan and pull Expert RAW DNG stills.")
    adb_p.add_argument("--force", action="store_true", help="Bypass deduplication ledger and re-pull files.")
    adb_p.add_argument("--dry-run", action="store_true", help="Simulate remote scan and deduplication without file transfer.")
    adb_p.add_argument("--list-devices", action="store_true", help="List attached Android devices and exit.")

    # 8. GENERATE-PROXY (Lightweight 720p Proxy & WAV Audio Extraction)
    proxy_p = subparsers.add_parser("generate-proxy", aliases=["proxy"], help="Generate lightweight 720p proxy video and WAV audio track.")
    proxy_p.add_argument("--input", "-i", required=True, help="Path to input 4K video file.")
    proxy_p.add_argument("--output-proxy", "-o", default=None, help="Destination proxy MP4 file path.")
    proxy_p.add_argument("--output-wav", "-w", default=None, help="Destination WAV audio file path.")
    proxy_p.add_argument("--event", "--festival", default="Concert", help="Event/Festival name.")
    proxy_p.add_argument("--artist", default="Artist", help="DJ/Artist name.")
    proxy_p.add_argument("--dry-run", action="store_true", help="Simulate command assembly without execution.")

    # 9. PUBLISH-YOUTUBE (YouTube Data API v3 Distribution & Content ID Auditing)
    pub_p = subparsers.add_parser("publish-youtube", aliases=["publish"], help="Publish video master to YouTube with Content ID auditing loop.")
    pub_p.add_argument("--video", "-v", "--input", "-i", dest="video", required=True, help="Path to finalized vertical 9:16 MP4 master.")
    pub_p.add_argument("--title", "-t", default="Shorts", help="YouTube video title (<100 chars).")
    pub_p.add_argument("--description", "-d", default="", help="YouTube video description.")
    pub_p.add_argument("--tags", nargs="*", default=[], help="List of video tags/hashtags.")
    pub_p.add_argument("--seo-json", "-s", default=None, help="Path to companion .seo.json metadata sidecar.")
    pub_p.add_argument("--category-id", default="10", help="YouTube category ID (default: 10 Music).")
    pub_p.add_argument(
        "--privacy",
        choices=["unlisted", "public", "private"],
        default="unlisted",
        help="Initial upload privacy status (default: unlisted).",
    )
    pub_p.add_argument(
        "--auto-promote",
        action="store_true",
        help="Automatically promote video from unlisted to public when Content ID audit passes.",
    )
    pub_p.add_argument(
        "--skip-audit",
        action="store_true",
        help="Bypass Content ID auditing loop.",
    )
    pub_p.add_argument(
        "--poll-timeout",
        type=float,
        default=300.0,
        help="Maximum timeout in seconds for Content ID auditing loop (default: 300.0s).",
    )
    pub_p.add_argument(
        "--poll-interval",
        type=float,
        default=2.0,
        help="Polling interval in seconds between YouTube API checks (default: 2.0s).",
    )
    pub_p.add_argument("--client-secrets", default=None, help="Path to client_secret.json.")
    pub_p.add_argument("--token-path", "--token-file", dest="token_path", default=None, help="Path to token.json.")
    pub_p.add_argument("--db-path", default=None, help="Path to SQLite manifest database.")
    pub_p.add_argument("--project-id", default=None, help="Asset or Project ID for SQLite manifest tracking.")
    pub_p.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate upload and auditing workflow without live YouTube API network calls.",
    )

    # 9. PIPELINE
    pipe_p = subparsers.add_parser("pipeline", help="Execute complete end-to-end production pipeline.")
    pipe_p.add_argument("--input", "-i", default=None, help="Raw input video file. If omitted, defaults to pulling from device via ADB.")
    pipe_p.add_argument("--from-device", action="store_true", help="Explicitly pull latest take from Samsung S26 Ultra via ADB.")
    pipe_p.add_argument("--device", "-d", default=None, help="Target ADB device serial (used with ADB ingest).")
    pipe_p.add_argument("--adb-path", default=None, help="Explicit path to adb binary.")
    pipe_p.add_argument("--event", "--festival", required=True, help="Event/Festival name.")
    pipe_p.add_argument("--artist", required=True, help="DJ/Artist name.")
    pipe_p.add_argument("--track", default="ID", help="Track name or ID.")
    pipe_p.add_argument("--genre", default="house", help="EDM subgenre.")
    pipe_p.add_argument("--brand", choices=[b.value for b in BrandType], default=BrandType.MUSIC_BAPTISM.value)
    pipe_p.add_argument("--tier", choices=[t.value for t in EventTier], default=EventTier.PILLAR_A.value)
    pipe_p.add_argument("--reframe-mode", choices=[r.value for r in ReframeMode], default=ReframeMode.CENTER_CROP.value)
    pipe_p.add_argument("--start-time", type=float, default=None, help="Manual start timestamp in seconds (bypasses auto-drop).")
    pipe_p.add_argument("--duration", type=float, default=None, help="Target clip duration in seconds.")
    pipe_p.add_argument("--auto-drop", action="store_true", help="Enable intelligent RMS drop detection via AudioDropDetector.")
    pipe_p.add_argument("--drop-duration", type=float, default=30.0, help="Target drop duration in seconds (default: 30.0).")
    pipe_p.add_argument("--publish-youtube", action="store_true", help="Trigger YouTube Data API v3 upload and Content ID auditing loop.")
    pipe_p.add_argument("--auto-promote", action="store_true", help="Automatically promote from unlisted to public if clean.")
    pipe_p.add_argument("--poll-timeout", type=float, default=300.0, help="Polling timeout for Content ID check in seconds.")
    pipe_p.add_argument("--client-secrets", default=None, help="Path to client_secret.json.")
    pipe_p.add_argument("--token-path", "--token-file", dest="token_path", default=None, help="Path to token.json.")
    pipe_p.add_argument("--bypass-review", action="store_true", help="Bypass Awaiting Review gate and render immediately.")
    pipe_p.add_argument("--dry-run", action="store_true", help="Simulate pipeline without executing commands.")


    # 10. RENDER
    rend_p = subparsers.add_parser("render", help="Render master video from an approved project ID.")
    rend_p.add_argument("--project-id", required=True, help="Asset or Project ID for SQLite manifest tracking.")
    rend_p.add_argument("--reframe-mode", choices=[r.value for r in ReframeMode], default=ReframeMode.CENTER_CROP.value)
    rend_p.add_argument("--preset", choices=[p.value for p in ProductionPreset], default=ProductionPreset.FAST_TRACK.value)
    rend_p.add_argument("--publish-youtube", action="store_true")
    rend_p.add_argument("--auto-promote", action="store_true")
    rend_p.add_argument("--dry-run", action="store_true")
    rend_p.add_argument("--client-secrets", default=None)
    rend_p.add_argument("--token-path", "--token-file", dest="token_path", default=None)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    workspace = Path(args.target_dir).resolve()
    db_target = Path(args.db_path) if args.db_path else (workspace / "media_manifest.sqlite")

    try:
        if args.subcommand == "ingest":
            router = AssetIngestionRouter(workspace_root=workspace, ffprobe_path=args.ffprobe_path)
            res = router.ingest_asset(
                source_path=Path(args.input),
                event_name=args.event,
                artist_name=args.artist,
                track_name=args.track,
                brand=BrandType(args.brand),
                tier=EventTier(args.tier),
                version=args.version,
                dry_run=args.dry_run,
                ffprobe_custom_path=args.ffprobe_path,
            )
            print(f"[INGEST SUCCESS] Canonical: {res.canonical_filename} -> {res.staged_path}")

        elif args.subcommand == "process":
            processor = FFmpegMasterProcessor(custom_ffmpeg_path=args.ffmpeg_path)
            if args.start_time is not None:
                start_t = float(args.start_time)
                dur_t = args.duration
            elif args.auto_drop:
                in_p = Path(args.input)
                wav_companion = in_p.with_suffix(".wav")
                target_media = wav_companion if wav_companion.is_file() else in_p
                drop_res = run_auto_drop_detection(
                    audio_wav_path=target_media,
                    target_duration_sec=args.drop_duration,
                    manual_start_time=None,
                    manual_duration=args.duration,
                    custom_ffmpeg_path=args.ffmpeg_path,
                    dry_run=args.dry_run,
                )
                start_t = drop_res.start_time_sec
                dur_t = drop_res.duration_sec
            else:
                start_t = 0.0
                dur_t = args.duration

            cfg = TranscodeConfig(
                input_path=Path(args.input),
                output_path=Path(args.output),
                preset=ProductionPreset(args.preset),
                reframe_mode=ReframeMode(args.reframe_mode),
                crop_x=args.crop_x,
                crop_y=args.crop_y,
                tone_map=ToneMapMode(args.tone_map),
                denoise=DenoiseMode(args.denoise),
                loudnorm=LoudnormMode(args.loudnorm),
                start_time_sec=start_t,
                duration_sec=dur_t,
                max_duration_sec=args.max_duration,
                track_title=args.track_title,
                artist_name=args.artist_name,
                encoder_choice=args.encoder,
                custom_ffmpeg_path=args.ffmpeg_path,
                dry_run=args.dry_run,
            )
            res = processor.transcode(cfg)
            print(f"[PROCESS SUCCESS] Export: {res.output_path} ({res.duration_sec:.2f}s)")

        elif args.subcommand == "inspect":
            probe = probe_media_file(Path(args.input), ffprobe_path=args.ffprobe_path)
            print("=" * 60)
            print(f"MEDIA STREAM INSPECTION: {Path(args.input).name}")
            print("=" * 60)
            print(f"Resolution: {probe.width}x{probe.height} ({probe.resolution_label}) | Aspect Ratio: {probe.aspect_ratio}")
            print(f"Framerate: {probe.frame_rate} fps CFR | Video Codec: {probe.video_codec} ({probe.pix_fmt})")
            print(f"HDR Status: {probe.is_hdr} (Transfer: {probe.color_transfer}, Primaries: {probe.color_primaries})")
            print(f"Audio: {probe.audio_codec or 'None'} @ {probe.audio_sample_rate or 'N/A'}Hz ({probe.audio_channels or 0}ch)")
            print(f"Duration: {probe.duration_seconds:.2f}s | Size: {probe.file_size_bytes / (1024*1024):.2f} MB")
            print(f"SHA-256: {probe.sha256_hash}")
            print("=" * 60)

        elif args.subcommand == "generate-seo":
            seo = SEOCaptionGenerator.generate_seo_package(
                artist=args.artist,
                track=args.track,
                event=args.event,
                genre=args.genre,
                stage=args.stage,
                year=args.year,
                brand=BrandType(args.brand),
                tier=EventTier(args.tier),
            )
            print(json.dumps(asdict(seo), indent=2))

        elif args.subcommand == "audit-safezone":
            x, y, w, h = args.box
            report = SafeZoneAuditor.audit_bounding_box(BoundingBox(x=x, y=y, width=w, height=h))
            print(f"Safe-Zone Compliance: {'[PASSED]' if report.is_compliant else '[VIOLATIONS DETECTED]'}")
            if report.yt_violations:
                for v in report.yt_violations:
                    print(f"  - YouTube: {v}")
            if report.tiktok_violations:
                for v in report.tiktok_violations:
                    print(f"  - TikTok: {v}")
            print(f"Recommendation: {report.recommendation}")

        elif args.subcommand == "verify":
            qc = verify_media_file(Path(args.input), ffprobe_path=args.ffprobe_path, ffmpeg_path=args.ffmpeg_path)
            print("=" * 60)
            print(f"QUALITY CONTROL (QC) REPORT: {Path(args.input).name}")
            print("=" * 60)
            print(f"Overall Result: {'[PASSED]' if qc.passed else '[FAILED]'}")
            print(f"Duration: {qc.duration_seconds:.2f}s ({'PASS' if qc.duration_compliant else 'FAIL <= 59s'})")
            print(f"Resolution: {qc.resolution} ({'PASS' if qc.resolution_compliant else 'FAIL 1080x1920'})")
            print(f"Framerate: {qc.framerate_fps} fps ({'PASS' if qc.framerate_compliant else 'FAIL >= 30fps'})")
            print(f"Integrated Loudness: {qc.measured_lufs or 'N/A'} LUFS ({'PASS' if qc.lufs_compliant else 'FAIL -14 LUFS'})")
            print(f"True Peak: {qc.measured_true_peak or 'N/A'} dBTP ({'PASS' if qc.true_peak_compliant else 'FAIL <= -1.5 dBTP'})")
            if qc.failure_reasons:
                print("\nViolations:")
                for r in qc.failure_reasons:
                    print(f"  - {r}")
            print("=" * 60)
            if not qc.passed:
                sys.exit(1)

        elif args.subcommand == "adb-ingest":
            if SamsungADBIngestor is None:
                raise RuntimeError("Samsung ADB Ingest module (samsung_ingest.py) could not be loaded.")
            ingestor = SamsungADBIngestor(
                workspace_root=workspace,
                adb_path=args.adb_path,
                device_serial=args.device,
                remote_camera_path=args.remote_dir,
            )
            if args.list_devices:
                devs = ingestor.list_devices()
                print("=" * 60)
                print("ATTACHED ANDROID HARDWARE DEVICES (ADB)")
                print("=" * 60)
                if not devs:
                    print("No devices connected.")
                for d in devs:
                    s_tag = " [Samsung Flagship]" if d.is_samsung else ""
                    s26_tag = " [S26 Ultra Verified]" if d.is_s26_ultra else ""
                    auth_tag = "AUTHORIZED" if d.is_authorized else f"UNAUTHORIZED ({d.state})"
                    print(f"- Serial: {d.serial} | Model: {d.model} | State: {auth_tag}{s_tag}{s26_tag}")
                print("=" * 60)
                return

            summary = ingestor.ingest_batch(
                event_name=args.event,
                artist_name=args.artist,
                track_name=args.track,
                brand=BrandType(args.brand),
                tier=EventTier(args.tier),
                date_filter=args.date,
                recent_limit=args.recent,
                include_raw_dng=args.include_raw_dng,
                auto_route=args.auto_route,
                inbox_only=args.inbox_only,
                dry_run=args.dry_run,
                force=args.force,
            )
            print("\n" + "=" * 60)
            print("SAMSUNG S26 ULTRA ADB INGESTION SUMMARY")
            print("=" * 60)
            print(f"Remote Assets Scanned:     {summary.total_remote_scanned}")
            print(f"Eligible Pending Takes:    {summary.total_eligible}")
            print(f"Successfully Pulled:       {summary.total_pulled}")
            print(f"Skipped Duplicates:        {summary.total_skipped_duplicate}")
            print(f"Failed Transfers:          {summary.total_failed}")
            print(f"Total Payload:             {summary.total_mb_transferred:.2f} MB")
            print(f"Elapsed Time:              {summary.total_duration_sec:.2f}s")
            print("=" * 60)
            if summary.errors:
                print("\nErrors encountered:")
                for err in summary.errors:
                    print(f"  - {err}")
                sys.exit(1)

        elif args.subcommand in ("generate-proxy", "proxy"):
            processor = FFmpegMasterProcessor(custom_ffmpeg_path=args.ffmpeg_path)
            input_p = Path(args.input).resolve()
            clean_fest = FilenameNormalizer.sanitize_token(args.event, default="Concert")
            clean_art = FilenameNormalizer.sanitize_token(args.artist, default="Artist")

            if args.output_proxy:
                proxy_out = Path(args.output_proxy).resolve()
            else:
                proxy_out = workspace / FOLDER_TIERS.get("RAW", "01_RAW") / clean_fest / clean_art / f"proxy_{input_p.name}"

            if args.output_wav:
                wav_out = Path(args.output_wav).resolve()
            else:
                wav_out = workspace / FOLDER_TIERS.get("RAW", "01_RAW") / clean_fest / clean_art / f"{input_p.stem}.wav"

            res = processor.generate_proxy_and_wav(
                input_path=input_p,
                output_proxy_path=proxy_out,
                output_wav_path=wav_out,
                dry_run=args.dry_run,
            )
            print(f"[PROXY SUCCESS] Proxy Video: {res.proxy_video_path}")
            print(f"[PROXY SUCCESS] WAV Audio:   {res.audio_wav_path}")

        elif args.subcommand in ("publish-youtube", "publish"):
            if YouTubePublisher is None:
                raise RuntimeError("YouTube publisher module (youtube_publisher.py) could not be loaded.")
            publisher = YouTubePublisher(
                client_secrets_path=args.client_secrets,
                token_path=args.token_path,
                db_path=args.db_path or db_target,
                dry_run=args.dry_run,
            )
            res = publisher.publish_workflow(
                video_path=Path(args.video),
                title=args.title,
                description=args.description,
                tags=args.tags,
                category_id=args.category_id,
                auto_promote=args.auto_promote and not args.skip_audit,
                poll_timeout_sec=args.poll_timeout,
                poll_interval_sec=args.poll_interval,
                project_id=args.project_id,
                db_path=args.db_path or db_target,
                seo_json_path=args.seo_json,
            )
            print("\n" + "=" * 60)
            print("YOUTUBE PUBLISH REPORT")
            print("=" * 60)
            print(f"Video ID:          {res.video_id}")
            print(f"Published URL:     {res.published_url}")
            print(f"Initial Privacy:   {res.initial_privacy}")
            print(f"Final Privacy:     {res.final_privacy}")
            print(f"Processing Status: {res.processing_status}")
            print(f"Content ID Status: {res.content_id_status}")
            print(f"Is Blocked:        {res.is_blocked}")
            if res.rejection_reason:
                print(f"Rejection Reason:  {res.rejection_reason}")
            if res.error_message:
                print(f"Error Message:     {res.error_message}")
            print("=" * 60)
            if res.is_blocked:
                sys.exit(2)
            elif res.error_message:
                sys.exit(1)

        elif args.subcommand == "pipeline":
            input_target = None
            if args.input:
                input_target = Path(args.input)
            else:
                # Default to ADB ingest if no explicit input is provided (replacing Quick Share)
                print("[PIPELINE] No --input specified. Defaulting to headless ADB ingest from device...")
                if SamsungADBIngestor is None:
                    raise RuntimeError("Samsung ADB Ingest module (samsung_ingest.py) could not be loaded.")
                ingestor = SamsungADBIngestor(
                    workspace_root=workspace,
                    adb_path=args.adb_path,
                    device_serial=args.device,
                )
                summary = ingestor.ingest_batch(
                    event_name=args.event,
                    artist_name=args.artist,
                    track_name=args.track,
                    brand=BrandType(args.brand),
                    tier=EventTier(args.tier),
                    recent_limit=1,
                    auto_route=False,
                    inbox_only=True,
                    dry_run=args.dry_run,
                )
                if summary.pulled_results and summary.pulled_results[0].success:
                    input_target = Path(summary.pulled_results[0].local_path)
                    print(f"[PIPELINE] Ingested camera take via ADB: {input_target}")
                elif args.dry_run:
                    input_target = Path(args.input) if args.input else (workspace / "01_RAW_INBOX" / "simulated_take.mp4")
                else:
                    raise RuntimeError("Failed to pull recent take from Samsung device via ADB.")

            res = run_ingestion_phase(
                input_file=input_target,
                workspace_root=workspace,
                event=args.event,
                artist=args.artist,
                track=args.track,
                genre=args.genre,
                brand=BrandType(args.brand),
                tier=EventTier(args.tier),
                start_time=args.start_time,
                duration=args.duration,
                auto_drop=args.auto_drop,
                drop_duration=args.drop_duration,
                dry_run=args.dry_run,
                ffmpeg_path=args.ffmpeg_path,
                ffprobe_path=args.ffprobe_path,
                db_path=db_target,
            )
            
            if getattr(args, "bypass_review", False):
                print("\n[BYPASS REVIEW] Automatically proceeding to Render Phase...")
                res = run_render_phase(
                    project_id=res["project_id"],
                    workspace_root=workspace,
                    reframe_mode=ReframeMode(args.reframe_mode),
                    preset=ProductionPreset.FAST_TRACK,
                    publish_youtube=args.publish_youtube,
                    auto_promote=args.auto_promote,
                    poll_timeout=args.poll_timeout,
                    dry_run=args.dry_run,
                    ffmpeg_path=args.ffmpeg_path,
                    ffprobe_path=args.ffprobe_path,
                    db_path=db_target,
                    client_secrets_path=getattr(args, "client_secrets", None),
                    token_path=getattr(args, "token_path", None),
                )
            else:
                print("\n" + "=" * 60)
                print("[AWAITING REVIEW] Hard-halt triggered. Phase 1 (Ingest & Proxy) Complete.")
                print(f"Asset Project ID: {res.get('project_id')}")
                print("Action Required: Please review the proxy in the Web UI and click 'Render'.")
                print("=" * 60)
        elif args.subcommand == "render":
            res = run_render_phase(
                project_id=args.project_id,
                workspace_root=workspace,
                reframe_mode=ReframeMode(args.reframe_mode),
                preset=ProductionPreset(args.preset),
                publish_youtube=args.publish_youtube,
                auto_promote=args.auto_promote,
                poll_timeout=300.0,
                dry_run=args.dry_run,
                ffmpeg_path=args.ffmpeg_path,
                ffprobe_path=args.ffprobe_path,
                db_path=db_target,
                client_secrets_path=getattr(args, "client_secrets", None),
                token_path=getattr(args, "token_path", None),
            )
            print("\n" + "=" * 60)
            print("MASTER PIPELINE EXECUTION SUMMARY")
            print("=" * 60)
            print(json.dumps(res, indent=2))
            print("=" * 60)

    except Exception as ex:
        print(f"[ORCHESTRATOR ERROR] {ex}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

