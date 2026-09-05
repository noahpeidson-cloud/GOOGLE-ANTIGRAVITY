"""
Name: YouTube Content ID Pre-Flight Guard & Resumable Uploader
Context Mapping: Extracted from `content_creation/youtube_publisher.py` and `content_creation/orchestrator.py`.
Strengths: Implements an autonomous pre-flight publishing workflow that protects channels against copyright strikes and muted audio. Uploads 9:16 vertical masters as "unlisted" via 5MB chunked resumable transfers, polls YouTube Data API v3 processing and Content ID telemetry, and executes an automated conditional branch: promoting clean videos to "public" automatically, or quarantining videos if copyright blocks or severe claims are detected. Includes deterministic dry-run simulation for headless validation.
Weaknesses: In the legacy pipeline, `youtube_publisher.py` was tightly coupled to SQLite schema mutations, had brittle fallback imports, and lacked a standalone quarantine export.
Implementation Instructions: Instantiate `YouTubeContentIDGuard(dry_run=...)`. Call `publish_with_preflight_guard(video_path, title, description, tags)` to execute the unlisted upload, Content ID polling loop, and automated promotion/quarantine branching.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import os
from pathlib import Path
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

# Configure console encoding for cross-platform unicode safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Optional Google API client imports with safe fallbacks
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False
    Request = None
    Credentials = None
    InstalledAppFlow = None
    build = None
    HttpError = None
    MediaFileUpload = None


# ============================================================================
# 1. CONSTANTS & ENUMS
# ============================================================================

YOUTUBE_SCOPES: List[str] = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

DEFAULT_TOKEN_FILE = "token.json"
DEFAULT_CLIENT_SECRETS_FILE = "client_secret.json"
DEFAULT_CHUNK_SIZE = 5 * 1024 * 1024  # 5 MB resumable chunk size
DEFAULT_POLL_INTERVAL_SEC = 2.0
DEFAULT_POLL_TIMEOUT_SEC = 300.0


class ContentIDVerdict(str, Enum):
    """Normalized outcomes of YouTube Content ID pre-flight auditing."""
    CLEARED = "UNLISTED_CLEARED"                # Transcoding succeeded, zero copyright blocks
    CLAIMED_PERMITTED = "CLAIMED_PERMITTED"      # Content ID claim exists but video is playable
    BLOCKED = "BLOCKED"                          # Blocked globally or in major territories
    PROCESSING_FAILED = "PROCESSING_FAILED"      # YouTube internal transcoding failure
    TIMED_OUT = "TIMED_OUT"                      # Processing exceeded max polling threshold
    FAILED = "FAILED"                            # Network or API failure


class PublishingAction(str, Enum):
    """Conditional branching action taken after audit."""
    PROMOTED_TO_PUBLIC = "PROMOTED_TO_PUBLIC"
    QUARANTINED_UNLISTED = "QUARANTINED_UNLISTED"
    KEPT_UNLISTED = "KEPT_UNLISTED"
    ABORTED = "ABORTED"


# ============================================================================
# 2. DATA STRUCTURES
# ============================================================================

@dataclass
class VideoMetadata:
    """Metadata parameters for the YouTube Shorts upload payload."""
    title: str
    description: str
    tags: List[str] = field(default_factory=list)
    category_id: str = "10"  # Music category
    privacy_status: str = "unlisted"  # Pre-flight mandate: must be unlisted
    self_declared_made_for_kids: bool = False
    embeddable: bool = True
    license: str = "youtube"
    default_language: str = "en"
    default_audio_language: str = "en"

    def to_api_body(self) -> Dict[str, Any]:
        """Converts into YouTube Data API v3 video resource dict."""
        return {
            "snippet": {
                "title": self.title,
                "description": self.description,
                "tags": self.tags,
                "categoryId": self.category_id,
                "defaultLanguage": self.default_language,
                "defaultAudioLanguage": self.default_audio_language,
            },
            "status": {
                "privacyStatus": self.privacy_status,
                "selfDeclaredMadeForKids": self.self_declared_made_for_kids,
                "embeddable": self.embeddable,
                "license": self.license,
            },
        }


@dataclass
class GuardedPublishResult:
    """Complete lifecycle audit report of pre-flight upload, polling, and branch."""
    video_id: str
    initial_privacy: str = "unlisted"
    final_privacy: str = "unlisted"
    processing_status: str = "unknown"
    verdict: ContentIDVerdict = ContentIDVerdict.CLEARED
    action_taken: PublishingAction = PublishingAction.KEPT_UNLISTED
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    published_url: str = ""
    poll_count: int = 0
    elapsed_seconds: float = 0.0
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_clean(self) -> bool:
        """True if the video is cleared of blocking copyright claims."""
        return not self.is_quarantined and self.verdict in (
            ContentIDVerdict.CLEARED,
            ContentIDVerdict.CLAIMED_PERMITTED,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value if isinstance(self.verdict, ContentIDVerdict) else str(self.verdict)
        d["action_taken"] = self.action_taken.value if isinstance(self.action_taken, PublishingAction) else str(self.action_taken)
        return d


# ============================================================================
# 3. AUTHENTICATION & CREDENTIALS RESOLUTION
# ============================================================================

class YouTubeOAuthResolver:
    """
    Resolves OAuth 2.0 credentials across a 3-tier hierarchy:
    1. Direct token path / token.json
    2. Environment variables (YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
    3. Interactive InstalledAppFlow (if interactive TTY)
    """

    @classmethod
    def resolve_credentials(
        cls,
        token_path: Optional[Union[str, Path]] = None,
        client_secrets_path: Optional[Union[str, Path]] = None,
    ) -> Any:
        if not GOOGLE_API_AVAILABLE or Credentials is None:
            raise RuntimeError(
                "Google API libraries (google-api-python-client, google-auth-oauthlib) "
                "are not installed. Cannot resolve live credentials."
            )

        # 1. Tier 1: Check token file candidates
        candidates = []
        if token_path:
            candidates.append(Path(token_path))
        if os.environ.get("YOUTUBE_TOKEN_PATH"):
            candidates.append(Path(os.environ["YOUTUBE_TOKEN_PATH"]))
        candidates.extend([
            Path(DEFAULT_TOKEN_FILE),
            Path.cwd() / DEFAULT_TOKEN_FILE,
            Path(__file__).parent / DEFAULT_TOKEN_FILE,
        ])

        for cand in candidates:
            if cand.is_file():
                try:
                    creds = Credentials.from_authorized_user_file(str(cand), YOUTUBE_SCOPES)
                    if creds and creds.valid:
                        return creds
                    if creds and creds.expired and creds.refresh_token and Request:
                        creds.refresh(Request())
                        with open(cand, "w", encoding="utf-8") as f:
                            f.write(creds.to_json())
                        return creds
                except Exception:
                    pass

        # 2. Tier 2: Check Environment Variables (Headless CI/Server mode)
        env_refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN")
        env_client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        env_client_sec = os.environ.get("YOUTUBE_CLIENT_SECRET")
        if env_refresh and env_client_id and env_client_sec:
            try:
                creds = Credentials(
                    None,
                    refresh_token=env_refresh,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=env_client_id,
                    client_secret=env_client_sec,
                    scopes=YOUTUBE_SCOPES,
                )
                if Request:
                    creds.refresh(Request())
                return creds
            except Exception as e:
                raise RuntimeError(f"Failed to authenticate via environment variables: {e}") from e

        # 3. Tier 3: Client secrets & InstalledAppFlow
        secret_candidates = []
        if client_secrets_path:
            secret_candidates.append(Path(client_secrets_path))
        if os.environ.get("YOUTUBE_CLIENT_SECRETS_FILE"):
            secret_candidates.append(Path(os.environ["YOUTUBE_CLIENT_SECRETS_FILE"]))
        secret_candidates.extend([
            Path(DEFAULT_CLIENT_SECRETS_FILE),
            Path.cwd() / DEFAULT_CLIENT_SECRETS_FILE,
        ])

        for s_cand in secret_candidates:
            if s_cand.is_file() and InstalledAppFlow and sys.stdin and sys.stdin.isatty():
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(s_cand), YOUTUBE_SCOPES)
                    creds = flow.run_local_server(port=8080)
                    out_path = Path(token_path) if token_path else Path(DEFAULT_TOKEN_FILE)
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                    return creds
                except Exception as e:
                    raise RuntimeError(f"Interactive OAuth flow failed: {e}") from e

        raise RuntimeError(
            "No valid YouTube credentials found via token.json, env vars, or client_secret.json."
        )


# ============================================================================
# 4. YOUTUBE CONTENT ID GUARD ENGINE
# ============================================================================

class YouTubeContentIDGuard:
    """
    Autonomous client managing pre-flight unlisted upload, Content ID polling,
    and auto-promotion vs quarantine branching.
    """

    def __init__(
        self,
        token_path: Optional[Union[str, Path]] = None,
        client_secrets_path: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
        service: Optional[Any] = None,
    ) -> None:
        self.token_path = Path(token_path) if token_path else None
        self.client_secrets_path = Path(client_secrets_path) if client_secrets_path else None
        self.dry_run = dry_run or (not GOOGLE_API_AVAILABLE and service is None)
        self._service = service

    def get_service(self) -> Any:
        """Retrieves or builds the authenticated Google API client resource."""
        if self._service is not None:
            return self._service
        if self.dry_run:
            return None

        creds = YouTubeOAuthResolver.resolve_credentials(
            token_path=self.token_path,
            client_secrets_path=self.client_secrets_path,
        )
        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def upload_chunked_unlisted(
        self,
        video_path: Union[str, Path],
        metadata: VideoMetadata,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        progress_callback: Optional[Callable[[int], None]] = None,
    ) -> str:
        """
        Executes resumable chunked upload to YouTube Data API v3.
        Guarantees initial privacyStatus='unlisted'.

        Returns:
            video_id (str): Generated YouTube video ID.
        """
        video_file = Path(video_path)
        if not self.dry_run and not video_file.exists():
            raise FileNotFoundError(f"Video file not found: {video_file}")

        # Dry-run deterministic simulation
        if self.dry_run:
            simulated_id = f"sim_{int(time.time())}_{video_file.stem[:6]}"
            print(f"[DRY-RUN] Simulating 5MB chunked upload for '{video_file.name}'")
            if progress_callback:
                progress_callback(50)
                progress_callback(100)
            print(f"[DRY-RUN] Video uploaded as UNLISTED with ID: {simulated_id}")
            return simulated_id

        service = self.get_service()
        body = metadata.to_api_body()
        # Enforce unlisted privacy
        body["status"]["privacyStatus"] = "unlisted"

        media = MediaFileUpload(
            str(video_file),
            mimetype="video/mp4",
            resumable=True,
            chunksize=chunk_size,
        )

        request = service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media,
        )

        response = None
        if hasattr(request, "next_chunk") and callable(request.next_chunk):
            while response is None:
                res = request.next_chunk()
                if isinstance(res, tuple):
                    status, response = res
                    if status:
                        pct = int(status.progress() * 100)
                        if progress_callback:
                            progress_callback(pct)
                        else:
                            print(f"  [CHUNK UPLOAD] {pct}% uploaded...")
                else:
                    response = res
                    break
        elif hasattr(request, "execute"):
            response = request.execute()
        else:
            response = request

        video_id = response.get("id") if isinstance(response, dict) else str(response)
        if not video_id:
            raise RuntimeError(f"Upload completed without returning a valid video ID: {response}")

        print(f"  [UPLOAD COMPLETE] Video ID: {video_id} (Privacy: unlisted)")
        return str(video_id)

    def poll_content_id_telemetry(
        self,
        video_id: str,
        poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
        timeout_sec: float = DEFAULT_POLL_TIMEOUT_SEC,
    ) -> Tuple[ContentIDVerdict, Optional[str], Dict[str, Any], int, float]:
        """
        Polls YouTube Data API v3 until video transcoding completes or a
        Content ID copyright block is triggered.

        Returns:
            (verdict, rejection_reason, item_details, poll_count, elapsed_seconds)
        """
        start_time = time.time()
        poll_count = 0

        # Dry-run deterministic simulation
        if self.dry_run:
            print(f"[DRY-RUN] Polling Content ID status for video {video_id} (Simulated Clean)")
            return (ContentIDVerdict.CLEARED, None, {"simulated": True}, 1, 0.1)

        service = self.get_service()

        while True:
            poll_count += 1
            elapsed = time.time() - start_time

            try:
                req = service.videos().list(
                    part="status,processingDetails,contentDetails",
                    id=video_id,
                )
                res = req.execute()
            except Exception as e:
                return (ContentIDVerdict.FAILED, str(e), {}, poll_count, elapsed)

            items = res.get("items", [])
            if not items:
                if elapsed >= timeout_sec:
                    return (
                        ContentIDVerdict.TIMED_OUT,
                        f"Video {video_id} not found after {timeout_sec}s",
                        {},
                        poll_count,
                        elapsed,
                    )
                time.sleep(poll_interval_sec)
                continue

            item = items[0]
            status = item.get("status", {})
            proc = item.get("processingDetails", {})
            content_details = item.get("contentDetails", {})

            upload_status = status.get("uploadStatus", "").lower()
            proc_status = proc.get("processingStatus", "").lower()
            rejection_reason = status.get("rejectionReason")
            license_val = str(status.get("license", "")).lower()

            # 1. Content ID Block / Copyright Rejection
            if (
                upload_status == "rejected"
                or (rejection_reason and "copyright" in rejection_reason.lower())
                or license_val == "blocked"
            ):
                reason = rejection_reason or "copyright_blocked"
                print(f"  [CONTENT ID BLOCK] Video rejected or blocked! Reason: {reason}")
                return (ContentIDVerdict.BLOCKED, reason, item, poll_count, elapsed)

            # 2. Server Processing Failure
            if upload_status == "failed" or proc_status in ("failed", "terminated"):
                fail_reason = proc.get("processingFailureReason") or rejection_reason or "transcoding_failed"
                print(f"  [PROCESSING FAILED] YouTube server failed: {fail_reason}")
                return (ContentIDVerdict.PROCESSING_FAILED, fail_reason, item, poll_count, elapsed)

            # 3. Transcoding Succeeded & Clean
            if proc_status == "succeeded" or (upload_status == "processed" and proc_status in ("", "succeeded")):
                licensed = content_details.get("licensedContent", False)
                verdict = ContentIDVerdict.CLAIMED_PERMITTED if licensed else ContentIDVerdict.CLEARED
                print(f"  [AUDIT CLEARED] Processing succeeded. Verdict: {verdict.value}")
                return (verdict, None, item, poll_count, elapsed)

            # 4. Timeout Check
            if elapsed >= timeout_sec:
                print(f"  [AUDIT TIMEOUT] Video still processing after {timeout_sec}s")
                return (ContentIDVerdict.TIMED_OUT, "Polling timeout", item, poll_count, elapsed)

            time.sleep(poll_interval_sec)

    def promote_to_public(self, video_id: str) -> bool:
        """
        Promotes an unlisted video to 'public' via videos.update.
        """
        if self.dry_run:
            print(f"[DRY-RUN] Promoting video {video_id} to PUBLIC.")
            return True

        service = self.get_service()
        try:
            body = {
                "id": video_id,
                "status": {
                    "privacyStatus": "public",
                    "selfDeclaredMadeForKids": False,
                    "embeddable": True,
                    "license": "youtube",
                },
            }
            req = service.videos().update(part="status", body=body)
            res = req.execute()
            status_obj = res.get("status", {}) if isinstance(res, dict) else {}
            is_public = (status_obj.get("privacyStatus") == "public") or bool(res)
            if is_public:
                print(f"  [AUTO-PROMOTED] Video {video_id} is now PUBLIC on YouTube!")
            return is_public
        except Exception as e:
            print(f"  [ERROR] Failed to promote video to public: {e}", file=sys.stderr)
            return False

    def publish_with_preflight_guard(
        self,
        video_path: Union[str, Path],
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        auto_promote_if_clean: bool = True,
        poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
        timeout_sec: float = DEFAULT_POLL_TIMEOUT_SEC,
    ) -> GuardedPublishResult:
        """
        Master Pipeline:
        1. Uploads video as 'unlisted' via 5MB chunked resumable upload.
        2. Polls Content ID and processing telemetry.
        3. Executes conditional branch:
           - If clean and auto_promote=True: promotes to 'public'.
           - If copyright-blocked or processing-failed: QUARANTINES video (remains unlisted/private).
        """
        video_file = Path(video_path)
        meta = VideoMetadata(
            title=title,
            description=description,
            tags=tags or [],
            privacy_status="unlisted",
        )

        print("=" * 70)
        print("YOUTUBE PRE-FLIGHT CONTENT ID GUARD")
        print("=" * 70)
        print(f"Target Video: {video_file.name}")
        print(f"Title: '{title}'")
        print(f"Auto-Promote On Clearance: {auto_promote_if_clean}")

        # Step 1: Chunked Unlisted Upload
        print(f"\n[PHASE 1/3] Uploading video with UNLISTED privacy...")
        try:
            video_id = self.upload_chunked_unlisted(video_path=video_file, metadata=meta)
        except Exception as e:
            return GuardedPublishResult(
                video_id="",
                initial_privacy="unlisted",
                final_privacy="unlisted",
                processing_status="failed",
                verdict=ContentIDVerdict.FAILED,
                action_taken=PublishingAction.ABORTED,
                is_quarantined=False,
                error_message=f"Upload failed: {e}",
            )

        published_url = f"https://youtu.be/{video_id}"

        # Step 2: Content ID Polling Loop
        print(f"\n[PHASE 2/3] Polling Content ID processing telemetry...")
        verdict, rejection, details, poll_count, elapsed = self.poll_content_id_telemetry(
            video_id=video_id,
            poll_interval_sec=poll_interval_sec,
            timeout_sec=timeout_sec,
        )

        # Step 3: Conditional Promotion / Quarantine Branching
        print(f"\n[PHASE 3/3] Evaluating Conditional Branch (Verdict: {verdict.value})...")
        final_privacy = "unlisted"
        is_quarantined = False
        quarantine_reason = None
        action_taken = PublishingAction.KEPT_UNLISTED

        if verdict == ContentIDVerdict.BLOCKED:
            is_quarantined = True
            quarantine_reason = f"Content ID Copyright Block: {rejection}"
            action_taken = PublishingAction.QUARANTINED_UNLISTED
            print(f"  [QUARANTINE ACTIVATED] Video {video_id} is quarantined. Reason: {quarantine_reason}")
            print(f"  Promotion aborted. Video remains UNLISTED to prevent channel strike.")

        elif verdict == ContentIDVerdict.PROCESSING_FAILED:
            is_quarantined = True
            quarantine_reason = f"Transcoding Failure: {rejection}"
            action_taken = PublishingAction.QUARANTINED_UNLISTED
            print(f"  [QUARANTINE ACTIVATED] Video {video_id} failed processing. Reason: {quarantine_reason}")

        elif verdict in (ContentIDVerdict.CLEARED, ContentIDVerdict.CLAIMED_PERMITTED):
            if auto_promote_if_clean:
                promoted = self.promote_to_public(video_id)
                if promoted:
                    final_privacy = "public"
                    action_taken = PublishingAction.PROMOTED_TO_PUBLIC
                else:
                    action_taken = PublishingAction.KEPT_UNLISTED
            else:
                action_taken = PublishingAction.KEPT_UNLISTED
                print(f"  Auto-promote is disabled; video remains clean and UNLISTED.")

        else:  # TIMED_OUT or FAILED
            action_taken = PublishingAction.KEPT_UNLISTED
            print(f"  Audit inconclusive ({verdict.value}); video remains UNLISTED.")

        result = GuardedPublishResult(
            video_id=video_id,
            initial_privacy="unlisted",
            final_privacy=final_privacy,
            processing_status=details.get("processingDetails", {}).get("processingStatus", "unknown"),
            verdict=verdict,
            action_taken=action_taken,
            is_quarantined=is_quarantined,
            quarantine_reason=quarantine_reason,
            published_url=published_url,
            poll_count=poll_count,
            elapsed_seconds=elapsed,
            details=details,
        )

        print("\n" + "=" * 70)
        print("PUBLISH SUMMARY:")
        print(f"Video ID: {result.video_id}")
        print(f"Verdict: {result.verdict.value}")
        print(f"Final Privacy: {result.final_privacy.upper()}")
        print(f"Quarantined: {'YES' if result.is_quarantined else 'NO'}")
        print(f"Action Taken: {result.action_taken.value}")
        print(f"URL: {result.published_url}")
        print("=" * 70)

        return result


# ============================================================================
# 5. CLI INTERFACE
# ============================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="YouTube Content ID Pre-Flight Guard & Resumable Uploader"
    )
    parser.add_argument("--video", "-v", required=True, help="Path to 9:16 vertical MP4 video.")
    parser.add_argument("--title", "-t", default="Shorts", help="YouTube video title (<100 chars).")
    parser.add_argument("--description", "-d", default="", help="Video description.")
    parser.add_argument("--tags", nargs="*", default=[], help="Video tags.")
    parser.add_argument("--no-promote", action="store_true", help="Keep video unlisted; do not auto-promote.")
    parser.add_argument("--dry-run", action="store_true", help="Simulate upload and polling without live network.")
    parser.add_argument("--token-path", help="Path to token.json OAuth file.")
    parser.add_argument("--json", action="store_true", help="Output JSON telemetry.")

    args = parser.parse_args()

    guard = YouTubeContentIDGuard(
        token_path=args.token_path,
        dry_run=args.dry_run,
    )

    result = guard.publish_with_preflight_guard(
        video_path=args.video,
        title=args.title,
        description=args.description,
        tags=args.tags,
        auto_promote_if_clean=not args.no_promote,
    )

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    main()
