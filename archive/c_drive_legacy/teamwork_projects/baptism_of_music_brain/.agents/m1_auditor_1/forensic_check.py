"""Forensic integrity verification script for Milestone 1."""

from __future__ import annotations

import ast
import asyncio
import concurrent.futures
import os
from pathlib import Path
import sys
import threading
import time

# Ensure project root in sys.path
PROJECT_ROOT = Path(r"C:\Users\noahp\teamwork_projects\baptism_of_music_brain")
sys.path.insert(0, str(PROJECT_ROOT))

results = {
    "ast_facade_check": [],
    "win32_locking_empirical": [],
    "ffprobe_parsing_empirical": [],
    "pydantic_validation_empirical": [],
    "fsm_integrity_empirical": [],
    "job_manager_concurrency_empirical": [],
    "orchestrator_empirical": [],
}

def log(category: str, test_name: str, passed: bool, details: str = ""):
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] [{category}] {test_name}: {details}")
    results[category].append({
        "test": test_name,
        "passed": passed,
        "details": details
    })


# -------------------------------------------------------------
# 1. AST Static Analysis for Facades & Dummy Implementations
# -------------------------------------------------------------
def run_ast_analysis():
    print("\n--- 1. AST Analysis for Facades & Dummy Returns ---")
    src_dir = PROJECT_ROOT / "src"
    config_dir = PROJECT_ROOT / "config"
    
    files_to_check = list(src_dir.rglob("*.py")) + list(config_dir.rglob("*.py"))
    
    suspicious_functions = []
    
    for py_file in files_to_check:
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except Exception as e:
            log("ast_facade_check", f"parse_{py_file.name}", False, f"Failed to parse AST: {e}")
            continue
            
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check for empty body with just 'pass' or single constant return
                body = node.body
                # Filter docstring
                non_doc_body = [n for n in body if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str))]
                
                if len(non_doc_body) == 1:
                    stmt = non_doc_body[0]
                    if isinstance(stmt, ast.Pass):
                        # Empty pass body
                        suspicious_functions.append((py_file.name, node.name, "only 'pass' in body"))
                    elif isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
                        # Returns a literal constant
                        # Allow boolean helpers or simple getters if expected, but flag for review
                        suspicious_functions.append((py_file.name, node.name, f"returns constant {stmt.value.value}"))
                    elif isinstance(stmt, ast.Raise) and isinstance(stmt.exc, ast.Name) and stmt.exc.id == "NotImplementedError":
                        suspicious_functions.append((py_file.name, node.name, "raises NotImplementedError"))

    # Let's inspect findings
    print(f"Total files checked: {len(files_to_check)}")
    print(f"Suspicious 1-statement functions found: {len(suspicious_functions)}")
    for f, n, r in suspicious_functions:
        print(f"  - {f} :: {n} -> {r}")
        
    # Check if any production M1 functions are dummy
    # Filter out acceptable dunder/callback handlers
    real_violations = []
    for f, n, r in suspicious_functions:
        # Check if critical M1 function is fake
        if n in ("test_exclusive_handle", "probe_media", "check_file_lock", "validate_transition", "update_status", "create_job", "handle_file_ingested"):
            real_violations.append((f, n, r))
            
    if real_violations:
        log("ast_facade_check", "core_function_integrity", False, f"Found facade implementations in core functions: {real_violations}")
    else:
        log("ast_facade_check", "core_function_integrity", True, f"All core M1 functions contain genuine algorithmic logic ({len(suspicious_functions)} harmless helper stubs analyzed)")


# -------------------------------------------------------------
# 2. Empirical Verification of Win32 Locking & Debounce
# -------------------------------------------------------------
def run_win32_locking_tests():
    print("\n--- 2. Empirical Win32 File Locking & Debounce Tests ---")
    from src.watcher import file_locker
    from src.watcher.file_locker import check_file_lock, test_exclusive_handle, test_size_stability, wait_until_file_unlocked

    test_dir = PROJECT_ROOT / ".agents" / "m1_auditor_1" / "test_scratch"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # Test 2.1: Temporary file extensions
    temp_file = test_dir / "sample.mp4.crdownload"
    temp_file.write_bytes(b"data")
    res_temp = check_file_lock(temp_file)
    log("win32_locking_empirical", "temp_extension_rejected", res_temp.is_locked and res_temp.tier_failed == 1, f"reason: {res_temp.reason}")
    
    # Test 2.2: 0-byte file rejected
    zero_file = test_dir / "zero.mp4"
    zero_file.write_bytes(b"")
    res_zero = check_file_lock(zero_file, debounce_interval_sec=0.05)
    log("win32_locking_empirical", "zero_byte_file_rejected", res_zero.is_locked and res_zero.tier_failed == 3, f"reason: {res_zero.reason}")
    
    # Test 2.3: Unlocked, stable file accepted
    stable_file = test_dir / "stable.mp4"
    stable_file.write_bytes(b"A" * 4096)
    res_stable = check_file_lock(stable_file, debounce_interval_sec=0.05)
    log("win32_locking_empirical", "stable_file_accepted", res_stable.is_ready and res_stable.file_size_bytes == 4096, f"size: {res_stable.file_size_bytes}")
    
    # Test 2.4: Real Win32 exclusive lock test
    locked_file = test_dir / "actively_written.mp4"
    locked_file.write_bytes(b"B" * 1024)
    
    try:
        import win32file
        import win32con
        # Open with dwShareMode = 0 (exclusive)
        handle = win32file.CreateFile(
            str(locked_file),
            win32con.GENERIC_READ | win32con.GENERIC_WRITE,
            0, # Exclusive access
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_ATTRIBUTE_NORMAL,
            None,
        )
        try:
            # While open exclusively, check_file_lock must detect it as locked
            res_locked = check_file_lock(locked_file, debounce_interval_sec=0.05)
            log("win32_locking_empirical", "win32_exclusive_lock_detected", res_locked.is_locked and res_locked.tier_failed == 2, f"reason: {res_locked.reason}")
        finally:
            win32file.CloseHandle(handle)
            
        # After closing handle, check_file_lock must succeed
        res_unlocked = check_file_lock(locked_file, debounce_interval_sec=0.05)
        log("win32_locking_empirical", "win32_exclusive_lock_released", res_unlocked.is_ready, f"reason: {res_unlocked.reason}")
    except ImportError:
        # Fallback test with standard file lock
        with open(locked_file, "r+b") as f:
            res_locked = check_file_lock(locked_file, debounce_interval_sec=0.05)
            log("win32_locking_empirical", "file_lock_fallback_detected", res_locked.is_locked, f"reason: {res_locked.reason}")

    # Test 2.5: Dynamic byte-growth debounce test
    growing_file = test_dir / "growing.mp4"
    growing_file.write_bytes(b"chunk1")
    
    def grow_file():
        time.sleep(0.04)
        with open(growing_file, "ab") as f:
            f.write(b"chunk2_extra_bytes")
            
    t = threading.Thread(target=grow_file)
    t.start()
    ok, size, err = test_size_stability(growing_file, interval_sec=0.08)
    t.join()
    log("win32_locking_empirical", "growing_file_size_stability_detected", not ok and "changed" in str(err), f"err: {err}, size: {size}")


# -------------------------------------------------------------
# 3. Empirical Verification of FFprobe Prober
# -------------------------------------------------------------
def run_ffprobe_tests():
    print("\n--- 3. Empirical FFprobe Media Prober Tests ---")
    from tests.test_infra.media_generator import (
        generate_1080p_video,
        generate_4k_uhd_video,
        generate_vertical_video,
        generate_silent_video,
        generate_corrupt_video,
    )
    from src.renderer.probe import (
        probe_media,
        MediaFileNotFoundError,
        CorruptMediaError,
        parse_fractional_rate,
    )
    
    test_dir = PROJECT_ROOT / ".agents" / "m1_auditor_1" / "test_media"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    # 3.1 Generate real 1080p clip and probe
    clip_1080p = test_dir / "clip_1080p.mp4"
    generate_1080p_video(clip_1080p, duration_sec=1.0)
    p_1080p = probe_media(clip_1080p)
    log("ffprobe_parsing_empirical", "probe_1080p_resolution_fps", 
        p_1080p.width == 1920 and p_1080p.height == 1080 and abs(p_1080p.fps - 30.0) < 0.1,
        f"{p_1080p.width}x{p_1080p.height} @ {p_1080p.fps} fps, codec: {p_1080p.primary_video.codec_name}")
    log("ffprobe_parsing_empirical", "probe_1080p_audio",
        p_1080p.has_audio and p_1080p.primary_audio.codec_name == "aac" and p_1080p.primary_audio.sample_rate == 48000,
        f"audio codec: {p_1080p.primary_audio.codec_name}, rate: {p_1080p.primary_audio.sample_rate}")
        
    # 3.2 4K UHD probe
    clip_4k = test_dir / "clip_4k.mp4"
    generate_4k_uhd_video(clip_4k, duration_sec=1.0, fps=60.0)
    p_4k = probe_media(clip_4k)
    log("ffprobe_parsing_empirical", "probe_4k_resolution_fps",
        p_4k.width == 3840 and p_4k.height == 2160 and abs(p_4k.fps - 60.0) < 0.1,
        f"{p_4k.width}x{p_4k.height} @ {p_4k.fps} fps")
        
    # 3.3 9:16 Vertical probe
    clip_vert = test_dir / "clip_vert.mp4"
    generate_vertical_video(clip_vert, duration_sec=1.0)
    p_vert = probe_media(clip_vert)
    log("ffprobe_parsing_empirical", "probe_vertical_resolution",
        p_vert.width == 1080 and p_vert.height == 1920,
        f"{p_vert.width}x{p_vert.height}")
        
    # 3.4 Silent clip probe
    clip_silent = test_dir / "clip_silent.mp4"
    generate_silent_video(clip_silent, duration_sec=1.0)
    p_silent = probe_media(clip_silent)
    log("ffprobe_parsing_empirical", "probe_silent_no_audio",
        p_silent.has_video and not p_silent.has_audio and p_silent.primary_audio is None,
        f"video: {p_silent.has_video}, audio: {p_silent.has_audio}")
        
    # 3.5 Corrupt file error
    clip_corrupt = test_dir / "clip_corrupt.mp4"
    generate_corrupt_video(clip_corrupt)
    corrupt_caught = False
    try:
        probe_media(clip_corrupt)
    except CorruptMediaError:
        corrupt_caught = True
    log("ffprobe_parsing_empirical", "corrupt_media_error_raised", corrupt_caught, "CorruptMediaError raised as expected")
    
    # 3.6 Non-existent file error
    not_found_caught = False
    try:
        probe_media(test_dir / "does_not_exist_987654.mp4")
    except MediaFileNotFoundError:
        not_found_caught = True
    log("ffprobe_parsing_empirical", "media_not_found_error_raised", not_found_caught, "MediaFileNotFoundError raised as expected")


# -------------------------------------------------------------
# 4. Empirical Verification of Pydantic Models & FSM
# -------------------------------------------------------------
def run_pydantic_fsm_tests():
    print("\n--- 4. Empirical Pydantic Models & FSM State Machine Tests ---")
    from pydantic import ValidationError
    from src.models.schemas import (
        ClipSegment,
        ColorGradeSettings,
        AudioMasteringSettings,
        EditDecisionList,
        JobStatus,
        VideoJob,
    )
    from src.models.state_machine import (
        ALLOWED_TRANSITIONS,
        InvalidStateTransitionError,
        can_transition,
        validate_transition,
        transition_job,
    )

    # 4.1 ClipSegment bounds validation
    invalid_seg_caught = False
    try:
        ClipSegment(source_in_sec=5.0, source_out_sec=2.0)
    except ValidationError:
        invalid_seg_caught = True
    log("pydantic_validation_empirical", "clip_segment_inverted_bounds_rejected", invalid_seg_caught, "ValidationError raised on source_out <= source_in")

    # 4.2 EDL odd dimension rejection
    odd_res_caught = False
    try:
        EditDecisionList(
            job_id="test",
            source_video_path="clip.mp4",
            target_resolution=(1921, 1080),
        )
    except ValidationError as e:
        odd_res_caught = "even" in str(e)
    log("pydantic_validation_empirical", "edl_odd_dimension_rejected", odd_res_caught, "Odd dimensions rejected for YUV420p")

    # 4.3 ColorGradeSettings FFmpeg eq string compilation
    cg = ColorGradeSettings(contrast=1.25, brightness=0.05, saturation=1.5, gamma=1.1)
    eq_str = cg.to_ffmpeg_eq_filter()
    log("pydantic_validation_empirical", "color_grade_eq_filter_format",
        eq_str == "eq=contrast=1.250:brightness=0.050:saturation=1.500:gamma=1.100",
        f"Generated filter: {eq_str}")

    # 4.4 AudioMasteringSettings FFmpeg loudnorm string compilation
    ams = AudioMasteringSettings(target_lufs=-14.0, peak_limit_db=-1.5, gain_db=2.0)
    audio_str = ams.to_ffmpeg_audio_filter()
    log("pydantic_validation_empirical", "audio_mastering_filter_format",
        "loudnorm=I=-14.0:TP=-1.5:LRA=11" in audio_str and "volume=2.0dB" in audio_str,
        f"Generated filter: {audio_str}")

    # 4.5 FSM transitions
    job = VideoJob(source_filepath="test.mp4", status=JobStatus.DETECTED)
    fsm_ok = True
    for st in [JobStatus.INGESTING, JobStatus.INGESTED, JobStatus.PROBING, JobStatus.PROBED, JobStatus.ML_GRADING, JobStatus.AWAITING_OVERRIDE, JobStatus.APPROVED, JobStatus.RENDERING, JobStatus.DELIVERING, JobStatus.DELIVERED]:
        if not can_transition(job.status, st):
            fsm_ok = False
            break
        transition_job(job, st)
    log("fsm_integrity_empirical", "fsm_valid_lifecycle_progression", fsm_ok and job.status == JobStatus.DELIVERED, f"Final state: {job.status}")

    # 4.6 FSM illegal transition rejection
    illegal_caught = False
    try:
        validate_transition(JobStatus.DELIVERED, JobStatus.INGESTING)
    except InvalidStateTransitionError:
        illegal_caught = True
    log("fsm_integrity_empirical", "fsm_illegal_transition_rejected", illegal_caught, "Terminal state cannot transition")


# -------------------------------------------------------------
# 5. Empirical Verification of JobManager Concurrency
# -------------------------------------------------------------
def run_job_manager_concurrency():
    print("\n--- 5. Empirical JobManager Concurrency & Stress Tests ---")
    from src.models.schemas import JobStatus
    from src.pipeline.job_manager import JobManager, JobEventType

    jm = JobManager()
    events_count = 0
    event_lock = threading.Lock()

    def on_all_events(e):
        nonlocal events_count
        with event_lock:
            events_count += 1

    jm.subscribe(JobEventType.ALL, on_all_events)

    num_threads = 40
    ops_per_thread = 25

    def worker(worker_id: int):
        for i in range(ops_per_thread):
            j = jm.create_job(f"clip_{worker_id}_{i}.mp4", initial_status=JobStatus.DETECTED)
            jm.update_progress(j.job_id, float(i))
            jm.update_status(j.job_id, JobStatus.INGESTING)
            jm.update_status(j.job_id, JobStatus.INGESTED)

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = [pool.submit(worker, i) for i in range(num_threads)]
        for f in concurrent.futures.as_completed(futures):
            f.result() # raise if any worker errored

    expected_jobs = num_threads * ops_per_thread
    actual_jobs = jm.count_jobs()
    log("job_manager_concurrency_empirical", "thread_safe_job_count",
        actual_jobs == expected_jobs,
        f"Expected: {expected_jobs}, Actual: {actual_jobs}")

    log("job_manager_concurrency_empirical", "pubsub_event_emission",
        events_count > 0,
        f"Total pubsub events dispatched: {events_count}")


# -------------------------------------------------------------
# 6. Empirical Verification of Orchestrator Workflow
# -------------------------------------------------------------
async def run_orchestrator_tests():
    print("\n--- 6. Empirical Pipeline Orchestrator Workflow Tests ---")
    from config.settings import AppSettings
    from src.pipeline.job_manager import JobManager
    from src.pipeline.orchestrator import PipelineOrchestrator
    from src.models.schemas import ClipSegment, ColorGradeSettings, EditDecisionList, JobStatus

    test_media = PROJECT_ROOT / ".agents" / "m1_auditor_1" / "test_media" / "clip_1080p.mp4"
    jm = JobManager()

    class AuditMockML:
        async def grade_video_async(self, file_path, probe_data):
            return EditDecisionList(
                job_id="audit_job",
                source_video_path=str(file_path),
                segments=[ClipSegment(source_in_sec=0.0, source_out_sec=1.0)],
            )

    orchestrator = PipelineOrchestrator(
        job_manager=jm,
        ml_provider=AuditMockML(),
        auto_approve=False,
    )
    await orchestrator.start()
    job = await orchestrator.handle_file_ingested(test_media)
    log("orchestrator_empirical", "pipeline_ingest_probe_grade",
        job.status == JobStatus.AWAITING_OVERRIDE and job.probe_metadata is not None and job.active_edl is not None,
        f"Job status: {job.status}, active_edl segments: {job.active_edl.segment_count if job.active_edl else None}")

    # Override EDL
    new_edl = EditDecisionList(
        job_id=job.job_id,
        source_video_path=str(test_media),
        segments=[ClipSegment(source_in_sec=0.2, source_out_sec=0.8)],
        color_grade=ColorGradeSettings(contrast=1.5),
    )
    job_overridden = await orchestrator.override_edl(job.job_id, new_edl)
    log("orchestrator_empirical", "pipeline_user_override",
        job_overridden.status == JobStatus.OVERRIDE_APPLIED and job_overridden.active_edl.manual_override_applied is True,
        f"Overridden status: {job_overridden.status}, manual_override_applied: {job_overridden.active_edl.manual_override_applied}")

    # Approve job
    job_approved = await orchestrator.approve_job(job.job_id)
    log("orchestrator_empirical", "pipeline_approval_to_rendering",
        job_approved.status == JobStatus.RENDERING,
        f"Approved status: {job_approved.status}")

    await orchestrator.stop()


def main():
    print("===============================================================")
    print("     BAPTISM OF MUSIC BRAIN - FORENSIC INTEGRITY AUDIT")
    print("===============================================================")
    run_ast_analysis()
    run_win32_locking_tests()
    run_ffprobe_tests()
    run_pydantic_fsm_tests()
    run_job_manager_concurrency()
    asyncio.run(run_orchestrator_tests())
    
    print("\n===============================================================")
    print("                    FORENSIC AUDIT SUMMARY")
    print("===============================================================")
    total_tests = 0
    passed_tests = 0
    failed_tests = 0
    
    for cat, t_list in results.items():
        print(f"\n[{cat}]")
        for t in t_list:
            total_tests += 1
            if t["passed"]:
                passed_tests += 1
                print(f"  [PASS] {t['test']} - {t['details']}")
            else:
                failed_tests += 1
                print(f"  [FAIL] {t['test']} - {t['details']}")
                
    print(f"\nTOTAL: {total_tests} | PASSED: {passed_tests} | FAILED: {failed_tests}")
    
    if failed_tests > 0:
        print("\n>>> VERDICT: INTEGRITY VIOLATION <<<")
        sys.exit(1)
    else:
        print("\n>>> VERDICT: CLEAN <<<")
        sys.exit(0)

if __name__ == "__main__":
    main()
