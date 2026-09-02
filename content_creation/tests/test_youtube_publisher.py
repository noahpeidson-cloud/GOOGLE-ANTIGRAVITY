"""
test_youtube_publisher.py - Unit Test Suite for YouTube Shorts Publisher & Content ID Auditing Engine

Comprehensive 100% Mocked Test Suite covering:
1. Dataclass structures & properties (YouTubePublishResult, YouTubeVideoMetadata).
2. Multi-tier OAuth 2.0 authentication hierarchy & token refresh logic.
3. Resumable unlisted video upload with chunked and direct execution payloads.
4. Content ID auditing polling loop (clean clearance, copyright block, failure, timeout, API error).
5. Unlisted to public promotion engine.
6. End-to-end publish workflow orchestration with auto-promotion, quarantine on block, and aliases.
7. SQLite lifecycle manifest database synchronization.
8. Standalone CLI argument parsing, dry-run mode, and exit codes.
"""

from datetime import datetime
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import AssetStatus, ContentIDStatus
from metadata_tracker import MediaManifestDB
from youtube_publisher import (
    AuditTimeoutError,
    ContentIDBlockError,
    VideoAuditStatus,
    VideoProcessingFailedError,
    YouTubeAuthError,
    YouTubeAuthManager,
    YouTubePublisher,
    YouTubePublishError,
    YouTubePublishResult,
    YouTubeUploadError,
    YouTubeVideoMetadata,
    build_parser,
    main,
)


class TestYouTubeDataStructures(unittest.TestCase):
    """Tests for dataclasses, metadata formatting, and helper properties."""

    def test_youtube_video_metadata_to_api_body(self):
        meta = YouTubeVideoMetadata(
            title="John Summit - Where You Are Live @ EDC 2026 #Shorts",
            description="High fidelity concert capture\n#Shorts #EDM",
            tags=["EDM", "Festival", "Shorts"],
            category_id="10",
            privacy_status="unlisted",
        )
        body = meta.to_api_body()
        self.assertIn("snippet", body)
        self.assertIn("status", body)
        self.assertEqual(body["snippet"]["title"], "John Summit - Where You Are Live @ EDC 2026 #Shorts")
        self.assertEqual(body["snippet"]["categoryId"], "10")
        self.assertEqual(body["snippet"]["tags"], ["EDM", "Festival", "Shorts"])
        self.assertEqual(body["status"]["privacyStatus"], "unlisted")
        self.assertFalse(body["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(body["status"]["embeddable"])

    def test_youtube_publish_result_properties(self):
        # Cleared result
        cleared = YouTubePublishResult(
            video_id="dQw4w9WgXcQ",
            initial_privacy="unlisted",
            final_privacy="public",
            processing_status="succeeded",
            content_id_status="UNLISTED_CLEARED",
            is_blocked=False,
            published_url="https://youtu.be/dQw4w9WgXcQ",
        )
        self.assertTrue(cleared.is_cleared)
        self.assertTrue(cleared.success)

        # Blocked result
        blocked = YouTubePublishResult(
            video_id="dQw4w9WgXcQ",
            initial_privacy="unlisted",
            final_privacy="unlisted",
            processing_status="terminated",
            content_id_status="BLOCKED",
            is_blocked=True,
            rejection_reason="copyright",
            published_url="https://youtu.be/dQw4w9WgXcQ",
            error_message="Content ID Block",
        )
        self.assertFalse(blocked.is_cleared)
        self.assertFalse(blocked.success)

    def test_youtube_publish_result_defaults(self):
        res = YouTubePublishResult(video_id="test_vid_123")
        self.assertEqual(res.video_id, "test_vid_123")
        self.assertEqual(res.initial_privacy, "unlisted")
        self.assertEqual(res.final_privacy, "unlisted")
        self.assertEqual(res.content_id_status, "UNCHECKED")
        self.assertFalse(res.is_blocked)
        self.assertIsNone(res.rejection_reason)
        self.assertEqual(res.poll_count, 0)


class TestYouTubeAuthentication(unittest.TestCase):
    """Tests for multi-tier authentication resolution, token refresh, and env fallback."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.token_file = Path(self.temp_dir.name) / "token.json"
        self.secret_file = Path(self.temp_dir.name) / "client_secret.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("youtube_publisher.Credentials")
    def test_token_file_valid_resolution(self, mock_creds_cls):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds

        # Write dummy token file
        self.token_file.write_text('{"token": "dummy"}', encoding="utf-8")

        resolved = YouTubeAuthManager.resolve_credentials(token_path=self.token_file)
        self.assertEqual(resolved, mock_creds)
        mock_creds_cls.from_authorized_user_file.assert_called_once()

    @patch("youtube_publisher.Request")
    @patch("youtube_publisher.Credentials")
    def test_token_file_expired_auto_refresh(self, mock_creds_cls, mock_req_cls):
        mock_creds = MagicMock()
        mock_creds.valid = False
        mock_creds.expired = True
        mock_creds.refresh_token = "mock_refresh_token"
        mock_creds.to_json.return_value = '{"refreshed": true}'
        mock_creds_cls.from_authorized_user_file.return_value = mock_creds

        self.token_file.write_text('{"token": "old"}', encoding="utf-8")

        resolved = YouTubeAuthManager.resolve_credentials(token_path=self.token_file)
        self.assertEqual(resolved, mock_creds)
        mock_creds.refresh.assert_called_once()
        self.assertIn("refreshed", self.token_file.read_text(encoding="utf-8"))

    @patch("youtube_publisher.Request")
    @patch("youtube_publisher.Credentials")
    def test_env_var_credentials_resolution(self, mock_creds_cls, mock_req_cls):
        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds_cls.return_value = mock_creds

        env_vars = {
            "YOUTUBE_REFRESH_TOKEN": "mock_refresh_12345",
            "YOUTUBE_CLIENT_ID": "mock_client_id.apps.googleusercontent.com",
            "YOUTUBE_CLIENT_SECRET": "mock_secret_xyz",
        }

        with patch.dict(os.environ, env_vars, clear=False):
            resolved = YouTubeAuthManager.resolve_credentials(token_path="/nonexistent/path/token.json")
            self.assertEqual(resolved, mock_creds)
            mock_creds_cls.assert_called_once_with(
                None,
                refresh_token="mock_refresh_12345",
                token_uri="https://oauth2.googleapis.com/token",
                client_id="mock_client_id.apps.googleusercontent.com",
                client_secret="mock_secret_xyz",
                scopes=unittest.mock.ANY,
            )
            mock_creds.refresh.assert_called_once()

    @patch("youtube_publisher.InstalledAppFlow")
    @patch("sys.stdin")
    def test_interactive_oauth_flow(self, mock_stdin, mock_flow_cls):
        mock_stdin.isatty.return_value = True
        mock_flow = MagicMock()
        mock_creds = MagicMock()
        mock_creds.to_json.return_value = '{"token": "flow_saved"}'
        mock_flow.run_local_server.return_value = mock_creds
        mock_flow_cls.from_client_secrets_file.return_value = mock_flow

        self.secret_file.write_text('{"installed": {}}', encoding="utf-8")

        resolved = YouTubeAuthManager.resolve_credentials(
            token_path=self.token_file,
            client_secrets_path=self.secret_file,
        )
        self.assertEqual(resolved, mock_creds)
        self.assertTrue(self.token_file.is_file())

    def test_headless_auth_failure_raises_youtube_auth_error(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(YouTubeAuthError):
                YouTubeAuthManager.resolve_credentials(
                    token_path=Path("/nonexistent/token.json"),
                    client_secrets_path=Path("/nonexistent/secret.json"),
                )

    def test_get_authenticated_service_dry_run(self):
        pub = YouTubePublisher(dry_run=True)
        self.assertIsNone(pub.get_authenticated_service())

    def test_get_authenticated_service_injected(self):
        mock_service = MagicMock()
        pub = YouTubePublisher(service=mock_service)
        self.assertEqual(pub.get_authenticated_service(), mock_service)


class TestYouTubePublisherUpload(unittest.TestCase):
    """Tests for video upload functionality."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_video = Path(self.temp_dir.name) / "test_master_1080p.mp4"
        self.test_video.write_bytes(b"Simulated MP4 byte stream for testing")

    def tearDown(self):
        self.temp_dir.cleanup()

    @patch("youtube_publisher.MediaFileUpload")
    def test_upload_unlisted_chunked_success(self, mock_media_cls):
        mock_service = MagicMock()
        mock_request = MagicMock()
        # Simulate resumable chunk progress then final response
        mock_status = MagicMock()
        mock_status.progress.return_value = 1.0
        mock_request.next_chunk.side_effect = [(mock_status, {"id": "mock_vid_98765"})]
        mock_service.videos().insert.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        video_id = publisher.upload_unlisted(
            video_path=self.test_video,
            title="Martin Garrix - Animals Live #Shorts",
            description="Live from Ultra 2026",
            tags=["Garrix", "Ultra"],
            category_id="10",
        )

        self.assertEqual(video_id, "mock_vid_98765")
        mock_service.videos().insert.assert_called_once()
        call_kwargs = mock_service.videos().insert.call_args[1]
        self.assertEqual(call_kwargs["part"], "snippet,status")
        self.assertEqual(call_kwargs["body"]["snippet"]["title"], "Martin Garrix - Animals Live #Shorts")
        self.assertEqual(call_kwargs["body"]["status"]["privacyStatus"], "unlisted")
        self.assertFalse(call_kwargs["body"]["status"]["selfDeclaredMadeForKids"])

    def test_upload_unlisted_direct_execute_success(self):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.execute.return_value = {"id": "mock_vid_direct_111"}
        # Deliberately remove next_chunk to test execute branch
        del mock_request.next_chunk
        mock_service.videos().insert.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        video_id = publisher.upload_unlisted(
            video_path=self.test_video,
            title="Direct Execute Test",
            description="Testing direct execute branch",
        )
        self.assertEqual(video_id, "mock_vid_direct_111")

    def test_upload_missing_file_raises_error(self):
        mock_service = MagicMock()
        publisher = YouTubePublisher(service=mock_service)
        with self.assertRaises(FileNotFoundError):
            publisher.upload_unlisted(
                video_path="/path/to/nonexistent/video.mp4",
                title="Test",
                description="Test",
            )

    def test_upload_api_error_raises_youtube_upload_error(self):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.execute.side_effect = Exception("HTTP 500 Internal Server Error")
        del mock_request.next_chunk
        mock_service.videos().insert.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        with self.assertRaises(YouTubeUploadError):
            publisher.upload_unlisted(
                video_path=self.test_video,
                title="Error Test",
                description="Error Desc",
            )

    def test_dry_run_upload_simulated_id(self):
        publisher = YouTubePublisher(dry_run=True)
        video_id = publisher.upload_unlisted(
            video_path=self.test_video,
            title="Dry Run Test",
            description="Dry Run Desc",
        )
        self.assertTrue(video_id.startswith("dry_run_"))


class TestYouTubePublisherContentIDPolling(unittest.TestCase):
    """Tests for Content ID polling loop (success, copyright block, server error, timeout, api error)."""

    def test_polling_loop_cleared_after_two_cycles(self):
        mock_service = MagicMock()
        mock_request = MagicMock()

        # Cycle 1: Processing -> Cycle 2: Succeeded with standard claim (licensedContent=True)
        cycle_1 = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "status": {"uploadStatus": "uploaded", "privacyStatus": "unlisted"},
                "processingDetails": {"processingStatus": "processing"},
                "contentDetails": {"licensedContent": False},
            }]
        }
        cycle_2 = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "status": {"uploadStatus": "processed", "privacyStatus": "unlisted"},
                "processingDetails": {"processingStatus": "succeeded"},
                "contentDetails": {"licensedContent": True},
            }]
        }
        mock_request.execute.side_effect = [cycle_1, cycle_2]
        mock_service.videos().list.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        with patch("time.sleep", return_value=None):
            result = publisher.poll_content_id_status("dQw4w9WgXcQ", poll_interval_sec=0.01, timeout_sec=10.0)

        self.assertEqual(result.video_id, "dQw4w9WgXcQ")
        self.assertEqual(result.processing_status, "succeeded")
        self.assertEqual(result.content_id_status, "UNLISTED_CLEARED")
        self.assertFalse(result.is_blocked)
        self.assertIsNone(result.rejection_reason)
        self.assertEqual(result.poll_count, 2)
        self.assertEqual(mock_service.videos().list.call_count, 2)

    def test_polling_loop_copyright_block_detection(self):
        mock_service = MagicMock()
        mock_request = MagicMock()

        block_response = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "status": {
                    "uploadStatus": "rejected",
                    "rejectionReason": "copyright",
                    "privacyStatus": "unlisted",
                },
                "processingDetails": {
                    "processingStatus": "terminated",
                    "processingFailureReason": "copyrightBlockGlobal",
                },
                "contentDetails": {"licensedContent": True},
            }]
        }
        mock_request.execute.return_value = block_response
        mock_service.videos().list.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("dQw4w9WgXcQ", poll_interval_sec=0.01, timeout_sec=10.0)

        self.assertEqual(result.content_id_status, "BLOCKED")
        self.assertTrue(result.is_blocked)
        self.assertEqual(result.rejection_reason, "copyright")
        self.assertIn("Content ID block", result.error_message)

    def test_polling_loop_license_blocked_detection(self):
        mock_service = MagicMock()
        mock_request = MagicMock()

        license_block_response = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "status": {
                    "privacyStatus": "unlisted",
                    "license": "blocked",
                },
                "processingDetails": {
                    "processingStatus": "failed",
                },
            }]
        }
        mock_request.execute.return_value = license_block_response
        mock_service.videos().list.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("dQw4w9WgXcQ", poll_interval_sec=0.01, timeout_sec=10.0)

        self.assertEqual(result.content_id_status, "BLOCKED")
        self.assertTrue(result.is_blocked)

    def test_polling_loop_processing_failure(self):
        mock_service = MagicMock()
        mock_request = MagicMock()

        failure_response = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "status": {"uploadStatus": "failed", "privacyStatus": "unlisted"},
                "processingDetails": {
                    "processingStatus": "failed",
                    "processingFailureReason": "transcodeFailedCodecUnsupported",
                },
            }]
        }
        mock_request.execute.return_value = failure_response
        mock_service.videos().list.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("dQw4w9WgXcQ", poll_interval_sec=0.01, timeout_sec=10.0)

        self.assertEqual(result.content_id_status, "FAILED")
        self.assertTrue(result.is_blocked)
        self.assertEqual(result.rejection_reason, "transcodeFailedCodecUnsupported")

    def test_polling_loop_timeout_handling(self):
        mock_service = MagicMock()
        mock_request = MagicMock()

        still_processing = {
            "items": [{
                "id": "dQw4w9WgXcQ",
                "status": {"uploadStatus": "uploaded", "privacyStatus": "unlisted"},
                "processingDetails": {"processingStatus": "processing"},
            }]
        }
        mock_request.execute.return_value = still_processing
        mock_service.videos().list.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        # Simulate immediate timeout via mocked time.time sequence
        with patch("time.time", side_effect=[100.0, 100.0, 450.0, 450.0]):
            with patch("time.sleep", return_value=None):
                result = publisher.poll_content_id_status("dQw4w9WgXcQ", poll_interval_sec=1.0, timeout_sec=300.0)

        self.assertEqual(result.content_id_status, "TIMED_OUT")
        self.assertFalse(result.is_blocked)
        self.assertIn("timed out", result.error_message)

    def test_polling_loop_api_network_error(self):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.execute.side_effect = Exception("503 Service Unavailable")
        mock_service.videos().list.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.poll_content_id_status("dQw4w9WgXcQ")
        self.assertEqual(result.content_id_status, "FAILED")
        self.assertIn("503 Service Unavailable", result.error_message)


class TestYouTubePublisherPromotion(unittest.TestCase):
    """Tests for unlisted to public promotion."""

    def test_promote_to_public_success(self):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.execute.return_value = {
            "id": "dQw4w9WgXcQ",
            "status": {"privacyStatus": "public"},
        }
        mock_service.videos().update.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        success = publisher.promote_to_public("dQw4w9WgXcQ")

        self.assertTrue(success)
        mock_service.videos().update.assert_called_once_with(
            part="status",
            body={
                "id": "dQw4w9WgXcQ",
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True,
                    "license": "youtube",
                },
            },
        )

    def test_promote_to_public_api_failure(self):
        mock_service = MagicMock()
        mock_request = MagicMock()
        mock_request.execute.side_effect = Exception("API 403 Forbidden")
        mock_service.videos().update.return_value = mock_request

        publisher = YouTubePublisher(service=mock_service)
        success = publisher.promote_to_public("dQw4w9WgXcQ")
        self.assertFalse(success)

    def test_promote_to_public_dry_run(self):
        publisher = YouTubePublisher(dry_run=True)
        self.assertTrue(publisher.promote_to_public("dQw4w9WgXcQ"))


class TestYouTubePublishWorkflow(unittest.TestCase):
    """Tests for full orchestrator publish workflow."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_video = Path(self.temp_dir.name) / "20260822_EDC_Summit_V1_1080p.mp4"
        self.test_video.write_bytes(b"Simulated MP4 bytes")
        self.test_db = Path(self.temp_dir.name) / "test_manifest.sqlite"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_workflow_full_success_promoted_and_synced(self):
        mock_service = MagicMock()

        # Mock Insert
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_summit_123"})
        mock_service.videos().insert.return_value = mock_insert

        # Mock List Poll (Clean)
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "items": [{
                "id": "vid_summit_123",
                "status": {"uploadStatus": "processed", "privacyStatus": "unlisted"},
                "processingDetails": {"processingStatus": "succeeded"},
                "contentDetails": {"licensedContent": False},
            }]
        }
        mock_service.videos().list.return_value = mock_list

        # Mock Update
        mock_update = MagicMock()
        mock_update.execute.return_value = {
            "id": "vid_summit_123",
            "status": {"privacyStatus": "public"},
        }
        mock_service.videos().update.return_value = mock_update

        publisher = YouTubePublisher(service=mock_service, db_path=self.test_db)
        result = publisher.publish_workflow(
            video_path=self.test_video,
            title="Summit - Where You Are Live #Shorts",
            description="EDC Orlando 2026",
            tags=["Summit", "EDC"],
            auto_promote=True,
            project_id="20260822_EDC_Summit_V1",
        )

        self.assertEqual(result.video_id, "vid_summit_123")
        self.assertEqual(result.final_privacy, "public")
        self.assertEqual(result.content_id_status, "UNLISTED_CLEARED")
        self.assertFalse(result.is_blocked)

        # Verify SQLite DB persistence
        db = MediaManifestDB(db_path=self.test_db)
        asset = db.get_asset("20260822_EDC_Summit_V1")
        self.assertIsNotNone(asset)
        self.assertEqual(asset["current_status"], "POSTED")
        self.assertEqual(asset["youtube_content_id_status"], "UNLISTED_CLEARED")
        self.assertEqual(asset["metadata"]["youtube_video_id"], "vid_summit_123")

    def test_workflow_copyright_block_aborts_promotion(self):
        mock_service = MagicMock()

        # Mock Insert
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_blocked_999"})
        mock_service.videos().insert.return_value = mock_insert

        # Mock List Poll (Blocked)
        mock_list = MagicMock()
        mock_list.execute.return_value = {
            "items": [{
                "id": "vid_blocked_999",
                "status": {
                    "uploadStatus": "rejected",
                    "rejectionReason": "copyright",
                    "privacyStatus": "unlisted",
                },
                "processingDetails": {"processingStatus": "terminated"},
            }]
        }
        mock_service.videos().list.return_value = mock_list

        publisher = YouTubePublisher(service=mock_service, db_path=self.test_db)
        result = publisher.publish_workflow(
            video_path=self.test_video,
            title="Copyright Block Track",
            description="Test",
            auto_promote=True,
            project_id="20260822_Blocked_V1",
        )

        self.assertEqual(result.final_privacy, "unlisted")
        self.assertTrue(result.is_blocked)
        self.assertEqual(result.content_id_status, "BLOCKED")
        mock_service.videos().update.assert_not_called()

        # Verify SQLite DB has BLOCKED status
        db = MediaManifestDB(db_path=self.test_db)
        asset = db.get_asset("20260822_Blocked_V1")
        self.assertEqual(asset["youtube_content_id_status"], "BLOCKED")

    def test_workflow_seo_json_sidecar_parsing(self):
        mock_service = MagicMock()
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_seo_sidecar"})
        mock_service.videos().insert.return_value = mock_insert

        seo_file = Path(self.temp_dir.name) / "test.seo.json"
        seo_file.write_text(
            json.dumps({
                "yt_title": "SEO Loaded Title #Shorts",
                "yt_description": "SEO Loaded Description",
                "hashtags": ["#SEO1", "#SEO2"],
            }),
            encoding="utf-8",
        )

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.publish_workflow(
            video_path=self.test_video,
            title="",  # Empty to trigger SEO JSON loading
            description="",
            seo_json_path=seo_file,
            auto_promote=False,
        )

        self.assertEqual(result.video_id, "vid_seo_sidecar")
        call_kwargs = mock_service.videos().insert.call_args[1]
        self.assertEqual(call_kwargs["body"]["snippet"]["title"], "SEO Loaded Title #Shorts")
        self.assertEqual(call_kwargs["body"]["snippet"]["description"], "SEO Loaded Description")
        self.assertEqual(call_kwargs["body"]["snippet"]["tags"], ["#SEO1", "#SEO2"])

    def test_workflow_auto_promote_disabled(self):
        mock_service = MagicMock()
        mock_insert = MagicMock()
        mock_insert.next_chunk.return_value = (None, {"id": "vid_unlisted_only"})
        mock_service.videos().insert.return_value = mock_insert

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.publish_workflow(
            video_path=self.test_video,
            title="Unlisted Video",
            description="Description",
            auto_promote=False,
        )
        self.assertEqual(result.video_id, "vid_unlisted_only")
        self.assertEqual(result.final_privacy, "unlisted")
        self.assertEqual(result.content_id_status, "UNCHECKED")
        mock_service.videos().list.assert_not_called()
        mock_service.videos().update.assert_not_called()

    def test_workflow_upload_failure_handling(self):
        mock_service = MagicMock()
        mock_insert = MagicMock()
        mock_insert.next_chunk.side_effect = Exception("Upload pipe broken")
        del mock_insert.execute
        mock_service.videos().insert.return_value = mock_insert

        publisher = YouTubePublisher(service=mock_service)
        result = publisher.publish_workflow(
            video_path=self.test_video,
            title="Fail Title",
            description="Fail Desc",
        )
        self.assertEqual(result.video_id, "")
        self.assertIn("Upload failed", result.error_message)

    def test_dry_run_workflow_simulation(self):
        publisher = YouTubePublisher(dry_run=True, db_path=self.test_db)
        result = publisher.publish_workflow(
            video_path=self.test_video,
            title="Dry Run Title",
            description="Dry Run Desc",
            auto_promote=True,
            project_id="20260822_DryRun_V1",
        )

        self.assertTrue(result.video_id.startswith("dry_run_"))
        self.assertEqual(result.final_privacy, "public")
        self.assertEqual(result.content_id_status, "UNLISTED_CLEARED")
        self.assertFalse(result.is_blocked)

    def test_workflow_aliases(self):
        publisher = YouTubePublisher(dry_run=True)
        res1 = publisher.publish_pipeline(
            video_path=self.test_video,
            title="Alias 1",
            description="Desc 1",
        )
        res2 = publisher.publish_with_audit(
            video_path=self.test_video,
            title="Alias 2",
            description="Desc 2",
        )
        self.assertTrue(res1.video_id.startswith("dry_run_"))
        self.assertTrue(res2.video_id.startswith("dry_run_"))


class TestYouTubePublisherManifestSync(unittest.TestCase):
    """Tests for SQLite manifest database synchronization."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_db = Path(self.temp_dir.name) / "sync_manifest.sqlite"
        self.db = MediaManifestDB(db_path=self.test_db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_sync_manifest_db_existing_record_update(self):
        self.db.upsert_asset(
            asset_id="20260822_Test_Existing",
            source_file_name="raw.mp4",
            canonical_name="20260822_Test_Existing_1080p.mp4",
            brand="laser_baptism",
            tier="pillar_a_stadium_arena",
            current_status=AssetStatus.READY_TO_POST,
        )

        res = YouTubePublishResult(
            video_id="yt_sync_123",
            final_privacy="public",
            content_id_status="UNLISTED_CLEARED",
            is_blocked=False,
            published_url="https://youtu.be/yt_sync_123",
        )

        YouTubePublisher.sync_manifest_db(self.test_db, "20260822_Test_Existing", res)

        updated = self.db.get_asset("20260822_Test_Existing")
        self.assertEqual(updated["current_status"], "POSTED")
        self.assertEqual(updated["youtube_content_id_status"], "UNLISTED_CLEARED")
        self.assertEqual(updated["metadata"]["youtube_video_id"], "yt_sync_123")
        self.assertEqual(updated["metadata"]["youtube_url"], "https://youtu.be/yt_sync_123")

    def test_sync_manifest_db_blocked_record(self):
        res = YouTubePublishResult(
            video_id="yt_blocked_456",
            final_privacy="unlisted",
            content_id_status="BLOCKED",
            is_blocked=True,
            rejection_reason="copyright",
            published_url="https://youtu.be/yt_blocked_456",
        )

        YouTubePublisher.sync_manifest_db(self.test_db, "20260822_New_Blocked", res)

        record = self.db.get_asset("20260822_New_Blocked")
        self.assertEqual(record["youtube_content_id_status"], "BLOCKED")
        self.assertEqual(record["metadata"]["youtube_rejection_reason"], "copyright")


class TestYouTubePublisherCLI(unittest.TestCase):
    """Tests for CLI parser and main execution entry point."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_video = Path(self.temp_dir.name) / "cli_test_video.mp4"
        self.test_video.write_bytes(b"CLI video bytes")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cli_parser_defaults_and_options(self):
        parser = build_parser()
        args = parser.parse_args([
            "--video", str(self.test_video),
            "--title", "CLI Title",
            "--auto-promote",
            "--poll-timeout", "120",
            "--dry-run",
        ])

        self.assertEqual(args.video, str(self.test_video))
        self.assertEqual(args.title, "CLI Title")
        self.assertTrue(args.auto_promote)
        self.assertEqual(args.poll_timeout, 120.0)
        self.assertTrue(args.dry_run)

    def test_cli_parser_full_arguments(self):
        parser = build_parser()
        args = parser.parse_args([
            "--video", "master.mp4",
            "--title", "Full Title",
            "--description", "Full Description",
            "--tags", "tag1", "tag2",
            "--seo-json", "master.mp4.seo.json",
            "--category-id", "10",
            "--privacy", "unlisted",
            "--auto-promote",
            "--skip-audit",
            "--poll-timeout", "600",
            "--poll-interval", "5",
            "--client-secrets", "custom_secret.json",
            "--token-path", "custom_token.json",
            "--db-path", "custom_manifest.sqlite",
            "--project-id", "20260822_Project_V1",
            "--dry-run",
        ])

        self.assertEqual(args.video, "master.mp4")
        self.assertEqual(args.tags, ["tag1", "tag2"])
        self.assertTrue(args.skip_audit)
        self.assertEqual(args.poll_interval, 5.0)
        self.assertEqual(args.project_id, "20260822_Project_V1")

    @patch("sys.argv", ["youtube_publisher.py", "--video", "test.mp4", "--dry-run"])
    @patch("youtube_publisher.YouTubePublisher.publish_workflow")
    def test_main_cli_execution_success(self, mock_workflow):
        mock_workflow.return_value = YouTubePublishResult(
            video_id="dry_run_123",
            final_privacy="public",
            content_id_status="UNLISTED_CLEARED",
            is_blocked=False,
            published_url="https://youtu.be/dry_run_123",
        )

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 0)

    @patch("sys.argv", ["youtube_publisher.py", "--video", "test.mp4", "--dry-run"])
    @patch("youtube_publisher.YouTubePublisher.publish_workflow")
    def test_main_cli_execution_blocked_exit_code_2(self, mock_workflow):
        mock_workflow.return_value = YouTubePublishResult(
            video_id="dry_run_blocked",
            final_privacy="unlisted",
            content_id_status="BLOCKED",
            is_blocked=True,
            rejection_reason="copyright",
            published_url="https://youtu.be/dry_run_blocked",
        )

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 2)

    @patch("sys.argv", ["youtube_publisher.py", "--video", "test.mp4", "--dry-run"])
    @patch("youtube_publisher.YouTubePublisher.publish_workflow")
    def test_main_cli_execution_error_exit_code_1(self, mock_workflow):
        mock_workflow.return_value = YouTubePublishResult(
            video_id="",
            final_privacy="unlisted",
            content_id_status="FAILED",
            is_blocked=False,
            published_url="",
            error_message="Fatal Upload Error",
        )

        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)


if __name__ == "__main__":
    unittest.main()
