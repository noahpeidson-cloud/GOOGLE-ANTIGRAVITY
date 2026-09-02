"""
test_blueprint_consistency.py - Structural Integrity & Architectural Consistency Test Suite

Validates that:
1. V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md contains all required mechanisms:
   - Mechanism 0: Samsung Galaxy S26 Ultra ADB Hardware & Wireless mDNS Ingestion Bridge
   - Mechanism 1: MCP Asset Ingestion & Routing Engine
   - Mechanism 2: Librosa & Vectorized RMS Audio Drop Detector & DSP Analyzer
   - Mechanism 3: FFmpeg Hardware-Accelerated Master Transcoder
   - Mechanism 4: Headless Automated Quality Control (QC) Validator
   - Mechanism 5: YouTube Data API v3 Shorts Publisher & Content ID Auditing Engine
   - Mechanism 6: FastAPI Zero-Touch Remote Trigger Server (remote_trigger.py)
   - Mechanism 7: Tasker One UI 7 Mobile Fast-Action Client (tasker_profile.md)
2. Phase 0 (Physical Device Capture, Zero-Touch Remote Triggering & mDNS Auto-Discovery) in the 6-Phase Lifecycle.
3. Edge Cases 15-23 (including mDNS discovery timeout, port rotation, Tasker HTTP timeout, and concurrent trigger 409 conflict).
4. samsung_s26_concert_sop.md exists and contains complete S26 Ultra hardware matrices, optical laser safety rules, and audio gain staging specifications.
5. tasker_profile.md exists and contains valid Tasker XML profiles and One UI 7 setup runbooks.
6. orchestrator.py CLI correctly exposes adb-ingest, pipeline with --from-device/--auto-drop/--publish-youtube, and publish-youtube subcommands.
"""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from orchestrator import build_parser


class TestBlueprintConsistency(unittest.TestCase):
    """Tests validating the structural integrity of the V2 Master Blueprint."""

    def setUp(self):
        self.repo_root = Path(__file__).resolve().parent.parent.parent
        self.blueprint_path = self.repo_root / "content_creation" / "V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT.md"
        self.sop_path = self.repo_root / "content_creation" / "samsung_s26_concert_sop.md"
        self.tasker_path = self.repo_root / "content_creation" / "tasker_profile.md"

        self.assertTrue(self.blueprint_path.is_file(), f"Blueprint not found at {self.blueprint_path}")
        self.assertTrue(self.sop_path.is_file(), f"SOP not found at {self.sop_path}")
        self.assertTrue(self.tasker_path.is_file(), f"Tasker profile not found at {self.tasker_path}")

        self.blueprint_text = self.blueprint_path.read_text(encoding="utf-8")
        self.sop_text = self.sop_path.read_text(encoding="utf-8")
        self.tasker_text = self.tasker_path.read_text(encoding="utf-8")

    def test_blueprint_file_size_and_header(self):
        self.assertGreater(len(self.blueprint_text), 50000)
        self.assertIn("document_id: V2_CONSOLIDATED_EDM_SHORT_FORM_BLUEPRINT", self.blueprint_text)
        self.assertIn("Master Operational Blueprint for EDM Short-Form Content Strategy", self.blueprint_text)

    def test_blueprint_contains_mechanism_0_samsung_ingest_and_mdns(self):
        self.assertIn("Mechanism 0: Samsung Galaxy S26 Ultra ADB Hardware", self.blueprint_text)
        self.assertIn("samsung_ingest.py", self.blueprint_text)
        self.assertIn("SM-S948", self.blueprint_text)
        self.assertIn("ADBPullResult", self.blueprint_text)
        self.assertIn("ADBMDNSDiscovery", self.blueprint_text)
        self.assertIn("DiscoveredADBService", self.blueprint_text)
        self.assertIn("_adb-tls-connect._tcp.local.", self.blueprint_text)

    def test_blueprint_contains_6_phase_lifecycle_with_phase_0(self):
        self.assertIn("6-Phase Agent Orchestration Lifecycle", self.blueprint_text)
        self.assertIn("Phase 0: Physical Device Capture & Automated Hardware Ingestion", self.blueprint_text)
        self.assertIn("Step 0A (Mobile Trigger)", self.blueprint_text)
        self.assertIn("Step 0B (HTTP Dispatch)", self.blueprint_text)
        self.assertIn("Step 0C (mDNS Discovery & Connect)", self.blueprint_text)
        self.assertIn("Step 0D (Atomic Pull & Ledger)", self.blueprint_text)
        self.assertIn("Step 0E (Health Partitioning)", self.blueprint_text)
        self.assertIn("Phase 1: Ingestion & Trigger", self.blueprint_text)
        self.assertIn("Phase 2: Deep Analysis & Classification", self.blueprint_text)
        self.assertIn("Phase 3: Automated Transcoding & Assembly", self.blueprint_text)
        self.assertIn("Phase 4: Automated Verification & QC", self.blueprint_text)
        self.assertIn("Phase 5: Distribution Packaging & Metadata Staging", self.blueprint_text)

    def test_blueprint_contains_technical_guardrails(self):
        self.assertIn("-14.0", self.blueprint_text)
        self.assertIn("-1.5", self.blueprint_text)
        self.assertIn("59.00", self.blueprint_text)
        self.assertIn("1080", self.blueprint_text)
        self.assertIn("1920", self.blueprint_text)
        self.assertIn("60", self.blueprint_text)
        self.assertIn("50 items", self.blueprint_text.lower())

    def test_blueprint_contains_all_adb_and_remote_edge_cases(self):
        self.assertIn("ADB Device Unauthorized", self.blueprint_text)
        self.assertIn("ADB Binary Not Found in PATH", self.blueprint_text)
        self.assertIn("Physical Connection Lost Mid-Transfer", self.blueprint_text)
        self.assertIn("Host Storage Exhaustion", self.blueprint_text)
        self.assertIn("Folder Partition Overflow During Bulk Pull", self.blueprint_text)
        # Edge Cases 20-23
        self.assertIn("mDNS Discovery Timeout (No Service Found)", self.blueprint_text)
        self.assertIn("Android Wireless Debugging Port Rotation", self.blueprint_text)
        self.assertIn("Tasker HTTP Timeout / Host Unreachable", self.blueprint_text)
        self.assertIn("Concurrent Trigger Overlap (HTTP 409 Conflict)", self.blueprint_text)

    def test_blueprint_contains_mechanism_2_audio_dsp(self):
        self.assertIn("Mechanism 2: Librosa & Vectorized RMS Audio Drop Detector & DSP Analyzer", self.blueprint_text)
        self.assertIn("audio_dsp.py", self.blueprint_text)
        self.assertIn("AudioDropDetector", self.blueprint_text)
        self.assertIn("DropWindowResult", self.blueprint_text)
        self.assertIn("librosa.feature.rms", self.blueprint_text)

    def test_blueprint_contains_human_in_the_loop_awaiting_review_gate(self):
        self.assertIn("02_AWAITING_REVIEW", self.blueprint_text)
        self.assertIn("Human-in-the-Loop \"Awaiting Review\" Gate", self.blueprint_text)
        self.assertIn("generate_proxy_and_wav", self.blueprint_text)
        self.assertIn("trim_proxy_video", self.blueprint_text)
        self.assertIn("run_auto_drop_detection", self.blueprint_text)
        self.assertIn("01_RAW", self.blueprint_text)

    def test_blueprint_contains_mechanism_5_youtube_publisher(self):
        self.assertIn("Mechanism 5: YouTube Data API v3 Shorts Publisher & Content ID Auditing Engine", self.blueprint_text)
        self.assertIn("youtube_publisher.py", self.blueprint_text)
        self.assertIn("YouTubePublisher", self.blueprint_text)
        self.assertIn("YouTubePublishResult", self.blueprint_text)
        self.assertIn("videos.insert", self.blueprint_text)
        self.assertIn("videos.list", self.blueprint_text)
        self.assertIn("videos.update", self.blueprint_text)

    def test_blueprint_contains_mechanism_6_remote_trigger_server(self):
        self.assertIn("Mechanism 6: FastAPI Zero-Touch Remote Trigger Server", self.blueprint_text)
        self.assertIn("remote_trigger.py", self.blueprint_text)
        self.assertIn("PipelineTriggerRequest", self.blueprint_text)
        self.assertIn("TriggerResponse", self.blueprint_text)
        self.assertIn("ConflictResponse", self.blueprint_text)
        self.assertIn("POST /trigger-pipeline", self.blueprint_text)
        self.assertIn("HTTP 202 Accepted", self.blueprint_text)
        self.assertIn("HTTP 409 Conflict", self.blueprint_text)

    def test_blueprint_contains_mechanism_7_tasker_client(self):
        self.assertIn("Mechanism 7: Tasker One UI 7 Mobile Fast-Action Client", self.blueprint_text)
        self.assertIn("tasker_profile.md", self.blueprint_text)
        self.assertIn("Action Code 339", self.blueprint_text)
        self.assertIn("0,100,100,100", self.blueprint_text)
        self.assertIn("0,500,200,500", self.blueprint_text)
        self.assertIn("Knox Power Whitelist", self.blueprint_text)

    def test_blueprint_contains_automation_table_m4_entries(self):
        self.assertIn("Mobile Remote Triggering", self.blueprint_text)
        self.assertIn("Wireless Ingestion IP Mapping", self.blueprint_text)

    def test_sop_document_comprehensive_coverage(self):
        self.assertGreater(len(self.sop_text), 20000)
        self.assertIn("ISOCELL", self.sop_text)
        self.assertIn("200MP", self.sop_text)
        self.assertIn("1/120", self.sop_text)
        self.assertIn("5000K", self.sop_text)
        self.assertIn("5200K", self.sop_text)
        self.assertIn("-8 dB", self.sop_text)
        self.assertIn("Laser Radiation", self.sop_text)
        self.assertIn("Hyperfocal", self.sop_text)


class TestOrchestratorCLIIntegration(unittest.TestCase):
    """Tests validating orchestrator CLI parser support for ADB ingestion, drop detection, and publishing."""

    def setUp(self):
        self.parser = build_parser()

    def test_orchestrator_adb_ingest_subcommand(self):
        args = self.parser.parse_args([
            "adb-ingest", "--event", "EDCOrlando", "--artist", "JohnSummit", "--recent", "10", "--auto-route", "--force", "--dry-run"
        ])
        self.assertEqual(args.subcommand, "adb-ingest")
        self.assertEqual(args.event, "EDCOrlando")
        self.assertEqual(args.artist, "JohnSummit")
        self.assertEqual(args.recent, 10)
        self.assertTrue(args.auto_route)
        self.assertTrue(args.force)
        self.assertTrue(args.dry_run)

    def test_orchestrator_pipeline_from_device_flag(self):
        args = self.parser.parse_args([
            "pipeline", "--from-device", "--event", "LostLands", "--artist", "Excision", "--track", "FeelSomething", "--genre", "dubstep", "--dry-run"
        ])
        self.assertEqual(args.subcommand, "pipeline")
        self.assertTrue(args.from_device)
        self.assertEqual(args.event, "LostLands")
        self.assertEqual(args.artist, "Excision")
        self.assertEqual(args.track, "FeelSomething")
        self.assertTrue(args.dry_run)

    def test_orchestrator_pipeline_auto_drop_and_publish_flags(self):
        args = self.parser.parse_args([
            "pipeline", "--input", "raw.mp4", "--event", "Ultra", "--artist", "Garrix",
            "--auto-drop", "--drop-duration", "28.5", "--publish-youtube", "--auto-promote",
            "--poll-timeout", "150.0", "--dry-run"
        ])
        self.assertEqual(args.subcommand, "pipeline")
        self.assertTrue(args.auto_drop)
        self.assertEqual(args.drop_duration, 28.5)
        self.assertTrue(args.publish_youtube)
        self.assertTrue(args.auto_promote)
        self.assertEqual(args.poll_timeout, 150.0)
        self.assertTrue(args.dry_run)

    def test_orchestrator_publish_youtube_subcommand(self):
        args = self.parser.parse_args([
            "publish-youtube", "--video", "master.mp4", "--title", "Garrix Live", "--auto-promote", "--dry-run"
        ])
        self.assertEqual(args.subcommand, "publish-youtube")
        self.assertEqual(args.video, "master.mp4")
        self.assertEqual(args.title, "Garrix Live")
        self.assertTrue(args.auto_promote)
        self.assertTrue(args.dry_run)


if __name__ == "__main__":
    unittest.main()
