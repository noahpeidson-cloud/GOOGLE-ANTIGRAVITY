"""
youtube_publisher.py - YouTube Data API v3 Shorts Publisher & Content ID Auditing Engine

Track 2: Content Creation (EDM Short-Form Media Engineering & Distribution)

Key Functions:
1. Multi-Tier OAuth 2.0 Authentication:
   CLI Flags -> Environment Variables (YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
   -> token.json -> Interactive OAuth Flow.
2. Resumable Pre-flight Video Upload:
   Uploads finalized 9:16 vertical MP4s (<=59.0s) as "unlisted" with Music category (10).
3. Automated Content ID Auditing Polling Loop:
   Polls videos.list for processingDetails and status to detect transcoding completion
   or copyright/rejection blocks before public release.
4. Automated Status Promotion:
   Promotes unlisted videos to "public" once cleared; aborts and quarantines if blocked.
5. Lifecycle Manifest Synchronization:
   Updates media_manifest.sqlite with POSTED / BLOCKED / UNLISTED_CLEARED status.
6. Standalone CLI & Programmatic Dry-Run Simulation Mode.
"""

import argparse
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple, Union

# Optional Google API Client Imports with Safe Fallbacks
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import Resource, build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    GOOGLE_API_AVAILABLE = True
except ImportError as e:
    raise RuntimeError(f"Failed to import googleapiclient. Ensure dependencies are installed via pip: {e}")

GOOGLE_API_AVAILABLE = True


# Import configuration and SQLite manifest tracker
try:
    from config import AssetStatus, ContentIDStatus, SAFE_ZONE_YOUTUBE
except ImportError:
    class AssetStatus(str, Enum):
        RAW_INBOX = "RAW_INBOX"
        IN_PROGRESS = "IN_PROGRESS"
        READY_TO_POST = "READY_TO_POST"
        POSTED = "POSTED"
        ARCHIVED = "ARCHIVED"

    class ContentIDStatus(str, Enum):
        UNCHECKED = "UNCHECKED"
        UNLISTED_CLEARED = "UNLISTED_CLEARED"
        CLAIMED = "CLAIMED"
        BLOCKED = "BLOCKED"

try:
    from metadata_tracker import MediaManifestDB
except ImportError:
    MediaManifestDB = None


# Configure console encoding for cross-platform unicode safety
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# ============================================================================
# CONSTANTS & ENUMS
# ============================================================================

YOUTUBE_UPLOAD_SCOPES: List[str] = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

DEFAULT_TOKEN_FILE = "token.json"
DEFAULT_CLIENT_SECRETS_FILE = "client_secret.json"
DEFAULT_CATEGORY_ID = "10"  # Music
DEFAULT_POLL_INTERVAL_SEC = 2.0
DEFAULT_POLL_TIMEOUT_SEC = 300.0


class VideoAuditStatus(str, Enum):
    """Normalized audit outcomes."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    CLEARED = "UNLISTED_CLEARED"
    CLAIMED = "CLAIMED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class YouTubeVideoMetadata:
    """Standardized metadata payload for YouTube Shorts uploads."""
    title: str
    description: str
    tags: List[str] = field(default_factory=list)
    category_id: str = DEFAULT_CATEGORY_ID
    privacy_status: str = "unlisted"
    self_declared_made_for_kids: bool = False
    embeddable: bool = True
    license: str = "youtube"
    default_language: str = "en"
    default_audio_language: str = "en"

    def to_api_body(self) -> Dict[str, Any]:
        """Converts to YouTube Data API v3 video resource payload."""
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
class YouTubePublishResult:
    """Comprehensive result of YouTube upload, auditing, and promotion lifecycle."""
    video_id: str
    initial_privacy: str = "unlisted"
    final_privacy: str = "unlisted"
    processing_status: str = "unknown"
    content_id_status: str = "UNCHECKED"  # 'UNLISTED_CLEARED', 'CLAIMED', 'BLOCKED', 'TIMED_OUT', 'FAILED'
    is_blocked: bool = False
    rejection_reason: Optional[str] = None
    published_url: str = ""
    error_message: Optional[str] = None
    poll_count: int = 0
    elapsed_seconds: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_cleared(self) -> bool:
        """Returns True if video successfully passed audit without copyright block."""
        return (
            not self.is_blocked
            and self.content_id_status in ("UNLISTED_CLEARED", "CLAIMED")
            and self.processing_status == "succeeded"
        )

    @property
    def success(self) -> bool:
        """Returns True if the publishing operation completed cleanly."""
        return not self.is_blocked and not self.error_message


# ============================================================================
# EXCEPTIONS
# ============================================================================

class YouTubePublishError(Exception):
    """Base exception for YouTube publishing operations."""
    pass


class YouTubeAuthError(YouTubePublishError):
    """Authentication or OAuth credential resolution error."""
    pass


class YouTubeUploadError(YouTubePublishError):
    """Error during video file upload."""
    pass


class ContentIDBlockError(YouTubePublishError):
    """Video rejected or blocked due to Content ID copyright restrictions."""
    pass


class VideoProcessingFailedError(YouTubePublishError):
    """Video processing or transcoding failed on YouTube infrastructure."""
    pass


class AuditTimeoutError(YouTubePublishError):
    """Content ID auditing loop timed out."""
    pass


# ============================================================================
# AUTHENTICATION MANAGER
# ============================================================================

class YouTubeAuthManager:
    """
    Resolves and refreshes OAuth 2.0 credentials across the 4-tier hierarchy:
    1. Direct CLI flags / explicit file paths
    2. Environment variables (YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET)
    3. Default filesystem paths (token.json, client_secret.json)
    4. Interactive OAuth 2.0 InstalledAppFlow (if interactive terminal)
    """

    @classmethod
    def resolve_credentials(
        cls,
        token_path: Optional[Union[str, Path]] = None,
        client_secrets_path: Optional[Union[str, Path]] = None,
        scopes: Optional[List[str]] = None,
    ) -> Any:
        """
        Resolves OAuth 2.0 Credentials using the hierarchy.
        Returns google.oauth2.credentials.Credentials instance.
        """
        target_scopes = scopes or YOUTUBE_UPLOAD_SCOPES

        # 1. Tier 1 & 3: Check explicit or default token.json path
        token_candidates: List[Path] = []
        if token_path:
            token_candidates.append(Path(token_path))
        if os.environ.get("YOUTUBE_TOKEN_PATH"):
            token_candidates.append(Path(os.environ["YOUTUBE_TOKEN_PATH"]))
        token_candidates.extend([
            Path(DEFAULT_TOKEN_FILE),
            Path(__file__).parent / DEFAULT_TOKEN_FILE,
            Path.cwd() / DEFAULT_TOKEN_FILE,
        ])

        for cand in token_candidates:
            if cand.is_file():
                try:
                    if Credentials is not None:
                        creds = Credentials.from_authorized_user_file(str(cand), target_scopes)
                        if creds and creds.valid:
                            return creds
                        if creds and creds.expired and creds.refresh_token:
                            if Request is not None:
                                creds.refresh(Request())
                                with open(cand, "w", encoding="utf-8") as f:
                                    f.write(creds.to_json())
                                return creds
                except Exception as e:
                    # Token file might be corrupted or incompatible; log and fall through
                    pass

        # 2. Tier 2: Check Environment Variables for Headless / CI execution
        env_refresh = os.environ.get("YOUTUBE_REFRESH_TOKEN")
        env_client_id = os.environ.get("YOUTUBE_CLIENT_ID")
        env_client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")
        env_token_uri = os.environ.get("YOUTUBE_TOKEN_URI", "https://oauth2.googleapis.com/token")

        if env_refresh and env_client_id and env_client_secret:
            if Credentials is not None:
                try:
                    creds = Credentials(
                        None,
                        refresh_token=env_refresh,
                        token_uri=env_token_uri,
                        client_id=env_client_id,
                        client_secret=env_client_secret,
                        scopes=target_scopes,
                    )
                    if Request is not None:
                        creds.refresh(Request())
                    return creds
                except Exception as e:
                    raise YouTubeAuthError(f"Failed to authenticate using environment variables: {e}") from e

        # 3. Tier 4: Client Secrets & Interactive InstalledAppFlow
        secret_candidates: List[Path] = []
        if client_secrets_path:
            secret_candidates.append(Path(client_secrets_path))
        if os.environ.get("YOUTUBE_CLIENT_SECRETS_FILE"):
            secret_candidates.append(Path(os.environ["YOUTUBE_CLIENT_SECRETS_FILE"]))
        secret_candidates.extend([
            Path(DEFAULT_CLIENT_SECRETS_FILE),
            Path(__file__).parent / DEFAULT_CLIENT_SECRETS_FILE,
            Path.cwd() / DEFAULT_CLIENT_SECRETS_FILE,
        ])

        found_secret: Optional[Path] = None
        for s_cand in secret_candidates:
            if s_cand.is_file():
                found_secret = s_cand
                break

        if found_secret and InstalledAppFlow is not None:
            # Check if environment is interactive (not headless CI)
            if sys.stdin and sys.stdin.isatty():
                try:
                    flow = InstalledAppFlow.from_client_secrets_file(str(found_secret), target_scopes)
                    creds = flow.run_local_server(port=8080)
                    save_dest = Path(token_path) if token_path else Path(DEFAULT_TOKEN_FILE)
                    with open(save_dest, "w", encoding="utf-8") as f:
                        f.write(creds.to_json())
                    return creds
                except Exception as e:
                    raise YouTubeAuthError(f"Interactive OAuth flow failed: {e}") from e

        raise YouTubeAuthError(
            "No valid YouTube OAuth credentials found.\n"
            "Please provide credentials via one of:\n"
            "  1. --token-path / --token-file or token.json\n"
            "  2. Environment variables: YOUTUBE_REFRESH_TOKEN, YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET\n"
            "  3. --client-secrets / client_secret.json (in interactive terminal)"
        )


# ============================================================================
# YOUTUBE PUBLISHER ENGINE
# ============================================================================

class YouTubePublisher:
    """
    Autonomous publishing engine for YouTube Shorts with Content ID pre-flight verification.
    """

    def __init__(
        self,
        client_secrets_file: Optional[Union[str, Path]] = None,
        token_file: Optional[Union[str, Path]] = None,
        client_secrets_path: Optional[Union[str, Path]] = None,
        token_path: Optional[Union[str, Path]] = None,
        db_path: Optional[Union[str, Path]] = None,
        dry_run: bool = False,
        service: Optional[Any] = None,
        api_client: Optional[Any] = None,
        **kwargs: Any,
    ) -> None:
        self.client_secrets_path = Path(client_secrets_path or client_secrets_file) if (client_secrets_path or client_secrets_file) else None
        self.token_path = Path(token_path or token_file) if (token_path or token_file) else None
        self.db_path = Path(db_path) if db_path else None
        self.dry_run = dry_run
        self._service = service or api_client or kwargs.get("api_client") or kwargs.get("service")

    def get_authenticated_service(self) -> Any:
        """Initializes and returns the YouTube Data API v3 service resource."""
        if self._service is not None:
            return self._service

        if self.dry_run:
            return None

        if not GOOGLE_API_AVAILABLE:
            raise YouTubeAuthError(
                "Google API client libraries (google-api-python-client, google-auth-oauthlib) "
                "are not installed. Cannot perform live YouTube operations without dependencies."
            )

        creds = YouTubeAuthManager.resolve_credentials(
            token_path=self.token_path,
            client_secrets_path=self.client_secrets_path,
            scopes=YOUTUBE_UPLOAD_SCOPES,
        )
        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return self._service

    def upload_unlisted(
        self,
        video_path: Union[str, Path],
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        category_id: str = DEFAULT_CATEGORY_ID,
    ) -> str:
        """
        Uploads a finalized vertical MP4 to YouTube with privacyStatus: 'unlisted',
        selfDeclaredMadeForKids: False, and categoryId: '10' (Music).

        Returns:
            video_id (str): The unique YouTube video ID.
        """
        video_file = Path(video_path)

        if not self.dry_run and not video_file.exists():
            raise FileNotFoundError(f"Master video file does not exist: {video_file}")

        tags = tags or []

        # In dry-run mode, generate a simulated deterministic video ID
        if self.dry_run:
            simulated_id = f"dry_run_{int(time.time())}_{video_file.stem[:8]}"
            print(f"[DRY-RUN] Simulating unlisted upload for '{video_file.name}' (Title: '{title}')")
            print(f"[DRY-RUN] Generated simulated Video ID: {simulated_id}")
            return simulated_id

        service = self.get_authenticated_service()

        metadata = YouTubeVideoMetadata(
            title=title,
            description=description,
            tags=tags,
            category_id=category_id,
            privacy_status="unlisted",
            self_declared_made_for_kids=False,
            embeddable=True,
            license="youtube",
        )
        body = metadata.to_api_body()

        if MediaFileUpload is None:
            raise YouTubeUploadError("MediaFileUpload is not available; missing googleapiclient.")

        media = MediaFileUpload(
            str(video_file),
            mimetype="video/mp4",
            resumable=True,
            chunksize=5 * 1024 * 1024,
        )

        try:
            request = service.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            # Resumable upload progress loop
            response = None
            if hasattr(request, "next_chunk") and callable(request.next_chunk):
                while response is None:
                    res = request.next_chunk()
                    if isinstance(res, tuple):
                        status, response = res
                        if status:
                            progress = int(status.progress() * 100)
                            print(f"  [UPLOAD PROGRESS] {progress}% uploaded...")
                    elif isinstance(res, dict):
                        response = res
                        break
                    else:
                        response = res
                        break
            elif hasattr(request, "execute") and callable(request.execute):
                response = request.execute()
            else:
                response = request

            if isinstance(response, dict):
                video_id = response.get("id")
            elif hasattr(response, "get"):
                video_id = response.get("id")
            else:
                video_id = str(response)

            if not video_id:
                raise YouTubeUploadError(f"Upload completed but no video ID returned: {response}")

            print(f"  [UPLOAD SUCCESS] Video ID: {video_id} (Privacy: unlisted)")
            return str(video_id)

        except Exception as e:
            if isinstance(e, YouTubeUploadError):
                raise
            raise YouTubeUploadError(f"Failed to upload video to YouTube: {e}") from e

    def poll_content_id_status(
        self,
        video_id: str,
        poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
        timeout_sec: float = DEFAULT_POLL_TIMEOUT_SEC,
    ) -> YouTubePublishResult:
        """
        Polls videos.list(part='status,processingDetails,contentDetails') until
        transcoding completes or a copyright block / rejection is identified.

        Returns:
            YouTubePublishResult with content_id_status and is_blocked.
        """
        start_time = time.time()
        published_url = f"https://youtu.be/{video_id}"

        # In dry-run mode, simulate immediate clean audit
        if self.dry_run:
            print(f"[DRY-RUN] Polling Content ID status for video {video_id} (Simulated Clean)")
            return YouTubePublishResult(
                video_id=video_id,
                initial_privacy="unlisted",
                final_privacy="unlisted",
                processing_status="succeeded",
                content_id_status="UNLISTED_CLEARED",
                is_blocked=False,
                rejection_reason=None,
                published_url=published_url,
                poll_count=1,
                elapsed_seconds=0.1,
                details={"simulated": True},
            )

        service = self.get_authenticated_service()
        poll_count = 0

        while True:
            poll_count += 1
            elapsed = time.time() - start_time

            try:
                request = service.videos().list(
                    part="status,processingDetails,contentDetails",
                    id=video_id,
                )
                response = request.execute()
            except Exception as e:
                return YouTubePublishResult(
                    video_id=video_id,
                    initial_privacy="unlisted",
                    final_privacy="unlisted",
                    processing_status="error",
                    content_id_status="FAILED",
                    is_blocked=False,
                    rejection_reason=None,
                    published_url=published_url,
                    error_message=f"API error during polling: {e}",
                    poll_count=poll_count,
                    elapsed_seconds=elapsed,
                )

            items = response.get("items", [])
            if not items:
                if elapsed >= timeout_sec:
                    return YouTubePublishResult(
                        video_id=video_id,
                        initial_privacy="unlisted",
                        final_privacy="unlisted",
                        processing_status="unknown",
                        content_id_status="TIMED_OUT",
                        is_blocked=False,
                        rejection_reason=None,
                        published_url=published_url,
                        error_message=f"Video {video_id} not found after {timeout_sec}s polling.",
                        poll_count=poll_count,
                        elapsed_seconds=elapsed,
                    )
                time.sleep(poll_interval_sec)
                continue

            item = items[0]
            status = item.get("status", {})
            processing = item.get("processingDetails", {})
            content_details = item.get("contentDetails", {})

            upload_status = status.get("uploadStatus", "").lower()
            processing_status = processing.get("processingStatus", "").lower()
            rejection_reason = status.get("rejectionReason")
            licensed_content = content_details.get("licensedContent", False)
            current_privacy = status.get("privacyStatus", "unlisted")

            # 1. Content ID Block or Outright Rejection
            license_val = str(status.get("license", "")).lower()
            if upload_status == "rejected" or (rejection_reason and rejection_reason.lower() == "copyright") or license_val == "blocked":
                reason = rejection_reason or ("copyright" if license_val == "blocked" else "rejected")
                print(f"  [CONTENT ID BLOCK] Video rejected! Reason: {reason}")
                return YouTubePublishResult(
                    video_id=video_id,
                    initial_privacy="unlisted",
                    final_privacy=current_privacy,
                    processing_status=processing_status or "terminated",
                    content_id_status="BLOCKED",
                    is_blocked=True,
                    rejection_reason=reason,
                    published_url=published_url,
                    error_message=f"Content ID block detected: rejectionReason='{reason}'",
                    poll_count=poll_count,
                    elapsed_seconds=elapsed,
                    details=item,
                )

            # 2. Server-side Processing Failure
            if upload_status == "failed" or processing_status in ("failed", "terminated"):
                fail_reason = processing.get("processingFailureReason") or rejection_reason or "processing_failed"
                print(f"  [PROCESSING FAILED] YouTube processing failed: {fail_reason}")
                return YouTubePublishResult(
                    video_id=video_id,
                    initial_privacy="unlisted",
                    final_privacy=current_privacy,
                    processing_status="failed",
                    content_id_status="FAILED",
                    is_blocked=True,
                    rejection_reason=fail_reason,
                    published_url=published_url,
                    error_message=f"YouTube server processing failed: {fail_reason}",
                    poll_count=poll_count,
                    elapsed_seconds=elapsed,
                    details=item,
                )

            # 3. Processing Succeeded & Clean
            if processing_status == "succeeded" or (upload_status == "processed" and processing_status in ("", "succeeded")):
                cid_status = "UNLISTED_CLEARED"
                print(f"  [AUDIT CLEARED] Video processed cleanly (LicensedContent: {licensed_content})")
                return YouTubePublishResult(
                    video_id=video_id,
                    initial_privacy="unlisted",
                    final_privacy=current_privacy,
                    processing_status="succeeded",
                    content_id_status=cid_status,
                    is_blocked=False,
                    rejection_reason=None,
                    published_url=published_url,
                    error_message=None,
                    poll_count=poll_count,
                    elapsed_seconds=elapsed,
                    details=item,
                )

            # 4. Check for Timeout
            if elapsed >= timeout_sec:
                print(f"  [AUDIT TIMEOUT] Video processing still '{processing_status}' after {timeout_sec}s")
                return YouTubePublishResult(
                    video_id=video_id,
                    initial_privacy="unlisted",
                    final_privacy=current_privacy,
                    processing_status=processing_status or "processing",
                    content_id_status="TIMED_OUT",
                    is_blocked=False,
                    rejection_reason=None,
                    published_url=published_url,
                    error_message=f"Content ID polling timed out after {timeout_sec}s",
                    poll_count=poll_count,
                    elapsed_seconds=elapsed,
                    details=item,
                )

            time.sleep(poll_interval_sec)

    def promote_to_public(self, video_id: str) -> bool:
        """
        Updates video privacyStatus from 'unlisted' to 'public' via videos.update.

        Returns:
            True if promotion succeeded, False otherwise.
        """
        if self.dry_run:
            print(f"[DRY-RUN] Simulating promotion of video {video_id} to 'public'")
            return True

        service = self.get_authenticated_service()

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
            request = service.videos().update(
                part="status",
                body=body,
            )
            response = request.execute()
            if isinstance(response, dict):
                status_obj = response.get("status", {})
                is_public = (status_obj.get("privacyStatus") == "public") or (response.get("id") == video_id)
            else:
                is_public = bool(response)
            if is_public:
                print(f"  [PROMOTED] Video {video_id} is now PUBLIC!")
            return is_public
        except Exception as e:
            print(f"  [ERROR] Failed to promote video {video_id} to public: {e}", file=sys.stderr)
            return False

    def publish_workflow(
        self,
        video_path: Union[str, Path],
        title: str,
        description: str,
        tags: Optional[List[str]] = None,
        category_id: str = DEFAULT_CATEGORY_ID,
        auto_promote: bool = True,
        poll_timeout_sec: float = DEFAULT_POLL_TIMEOUT_SEC,
        poll_interval_sec: float = DEFAULT_POLL_INTERVAL_SEC,
        project_id: Optional[str] = None,
        db_path: Optional[Union[str, Path]] = None,
        seo_json_path: Optional[Union[str, Path]] = None,
    ) -> YouTubePublishResult:
        """
        Orchestrates full distribution lifecycle:
        1. Upload vertical video with unlisted privacy
        2. Poll Content ID telemetry until cleared or blocked
        3. If auto_promote=True and audit cleared -> promote to public
        4. Synchronize state with SQLite media_manifest.sqlite
        """
        tags = tags or []

        # 1. Inspect SEO JSON sidecar if provided and title/description are defaults
        if seo_json_path:
            seo_p = Path(seo_json_path)
            if seo_p.is_file():
                try:
                    with open(seo_p, "r", encoding="utf-8") as f:
                        seo_data = json.load(f)
                    if not title or title == "Shorts":
                        title = seo_data.get("yt_title") or seo_data.get("title") or title
                    if not description:
                        description = seo_data.get("yt_description") or seo_data.get("description") or description
                    if not tags:
                        tags = seo_data.get("hashtags") or seo_data.get("tags") or tags
                except Exception as e:
                    print(f"  [WARNING] Could not parse SEO JSON '{seo_json_path}': {e}", file=sys.stderr)

        # 2. Upload video as unlisted
        print(f"\n[PHASE 1/3] Uploading master video (privacy: unlisted)...")
        try:
            video_id = self.upload_unlisted(
                video_path=video_path,
                title=title,
                description=description,
                tags=tags,
                category_id=category_id,
            )
        except Exception as e:
            return YouTubePublishResult(
                video_id="",
                initial_privacy="unlisted",
                final_privacy="unlisted",
                processing_status="failed",
                content_id_status="FAILED",
                is_blocked=False,
                rejection_reason=None,
                published_url="",
                error_message=f"Upload failed: {e}",
            )

        # 3. Content ID Auditing Polling Loop
        if auto_promote:
            print(f"\n[PHASE 2/3] Auditing Content ID status (Timeout: {poll_timeout_sec}s)...")
            audit_result = self.poll_content_id_status(
                video_id=video_id,
                poll_interval_sec=poll_interval_sec,
                timeout_sec=poll_timeout_sec,
            )

            final_privacy = "unlisted"
            if not audit_result.is_blocked and audit_result.processing_status == "succeeded":
                print(f"\n[PHASE 3/3] Promoting video to PUBLIC...")
                promoted = self.promote_to_public(video_id)
                final_privacy = "public" if promoted else "unlisted"
            else:
                print(f"\n[PHASE 3/3] Promotion skipped (Blocked: {audit_result.is_blocked}, Status: {audit_result.content_id_status})")

            publish_result = YouTubePublishResult(
                video_id=video_id,
                initial_privacy="unlisted",
                final_privacy=final_privacy,
                processing_status=audit_result.processing_status,
                content_id_status=audit_result.content_id_status,
                is_blocked=audit_result.is_blocked,
                rejection_reason=audit_result.rejection_reason,
                published_url=audit_result.published_url,
                error_message=audit_result.error_message,
                poll_count=audit_result.poll_count,
                elapsed_seconds=audit_result.elapsed_seconds,
                details=audit_result.details,
            )
        else:
            print(f"\n[PHASE 2/3] Auto-promote disabled; video remains UNLISTED.")
            publish_result = YouTubePublishResult(
                video_id=video_id,
                initial_privacy="unlisted",
                final_privacy="unlisted",
                processing_status="uploaded",
                content_id_status="UNCHECKED",
                is_blocked=False,
                rejection_reason=None,
                published_url=f"https://youtu.be/{video_id}",
            )

        # 4. Manifest Database Synchronization
        target_db = db_path or self.db_path
        if target_db:
            try:
                self.sync_manifest_db(
                    db_path=Path(target_db),
                    asset_id=project_id or Path(video_path).stem,
                    publish_result=publish_result,
                )
            except Exception as e:
                print(f"  [WARNING] Failed to sync with manifest database: {e}", file=sys.stderr)

        return publish_result

    # Method aliases for architectural compatibility
    publish_pipeline = publish_workflow
    publish_with_audit = publish_workflow
    audit_content_id = poll_content_id_status

    @staticmethod
    def sync_manifest_db(
        db_path: Path,
        asset_id: str,
        publish_result: YouTubePublishResult,
    ) -> None:
        """
        Synchronizes publishing outcome to SQLite media_manifest.sqlite.
        Updates current_status to POSTED if public, and sets youtube_content_id_status.
        """
        if MediaManifestDB is None:
            return

        db = MediaManifestDB(db_path=db_path)
        existing = db.get_asset(asset_id)

        # Map publishing status to ContentIDStatus
        if publish_result.is_blocked:
            cid_status = ContentIDStatus.BLOCKED
        elif publish_result.content_id_status == "UNLISTED_CLEARED":
            cid_status = ContentIDStatus.UNLISTED_CLEARED
        elif publish_result.content_id_status == "CLAIMED":
            cid_status = ContentIDStatus.CLAIMED
        else:
            cid_status = ContentIDStatus.UNCHECKED

        # Determine asset lifecycle status
        if publish_result.final_privacy == "public":
            new_status = AssetStatus.POSTED
        elif existing:
            new_status = AssetStatus(existing["current_status"])
        else:
            new_status = AssetStatus.READY_TO_POST

        meta = existing.get("metadata", {}) if existing else {}
        meta["youtube_video_id"] = publish_result.video_id
        meta["youtube_url"] = publish_result.published_url
        meta["youtube_privacy"] = publish_result.final_privacy
        meta["youtube_cid_status"] = publish_result.content_id_status
        meta["youtube_published_at"] = datetime.now().isoformat()
        if publish_result.rejection_reason:
            meta["youtube_rejection_reason"] = publish_result.rejection_reason

        if existing:
            db.upsert_asset(
                asset_id=asset_id,
                source_file_name=existing["source_file_name"],
                canonical_name=existing["canonical_name"],
                brand=existing["brand"],
                tier=existing["tier"],
                event_name=existing.get("event_name"),
                artist_name=existing.get("artist_name"),
                track_name=existing.get("track_name"),
                genre=existing.get("genre"),
                duration_seconds=existing.get("duration_seconds"),
                is_hdr=bool(existing.get("is_hdr", 0)),
                measured_lufs=existing.get("measured_lufs"),
                measured_true_peak=existing.get("measured_true_peak"),
                current_status=new_status,
                youtube_content_id_status=cid_status,
                safe_zone_verified=bool(existing.get("safe_zone_verified", 0)),
                raw_path=existing.get("raw_path"),
                master_path=existing.get("master_path"),
                metadata_dict=meta,
            )
        else:
            db.upsert_asset(
                asset_id=asset_id,
                source_file_name=f"{asset_id}.mp4",
                canonical_name=f"{asset_id}.mp4",
                brand="music_baptism",
                tier="pillar_a_stadium_arena",
                current_status=new_status,
                youtube_content_id_status=cid_status,
                metadata_dict=meta,
            )
        print(f"  [MANIFEST SYNC] Updated asset '{asset_id}': status={new_status.value}, cid_status={cid_status.value}")


# ============================================================================
# CLI INTERFACE & ENTRY POINT
# ============================================================================

def build_parser() -> argparse.ArgumentParser:
    """Builds argument parser for youtube_publisher.py CLI."""
    parser = argparse.ArgumentParser(
        description="YouTube Shorts Publisher & Content ID Auditing Engine (Track 2: Content Creation)"
    )
    parser.add_argument("--video", "-v", required=True, help="Path to finalized vertical 9:16 MP4 master.")
    parser.add_argument("--title", "-t", default="Shorts", help="YouTube video title (<100 chars).")
    parser.add_argument("--description", "-d", default="", help="YouTube video description.")
    parser.add_argument("--tags", nargs="*", default=[], help="List of video tags/hashtags.")
    parser.add_argument("--seo-json", "-s", default=None, help="Path to companion .seo.json metadata sidecar.")
    parser.add_argument("--category-id", default=DEFAULT_CATEGORY_ID, help="YouTube category ID (default: 10 Music).")
    parser.add_argument(
        "--privacy",
        choices=["unlisted", "public", "private"],
        default="unlisted",
        help="Initial upload privacy status (default: unlisted).",
    )
    parser.add_argument(
        "--auto-promote",
        action="store_true",
        help="Automatically promote video from unlisted to public when Content ID audit passes.",
    )
    parser.add_argument(
        "--skip-audit",
        action="store_true",
        help="Bypass Content ID auditing loop.",
    )
    parser.add_argument(
        "--poll-timeout",
        type=float,
        default=DEFAULT_POLL_TIMEOUT_SEC,
        help="Maximum timeout in seconds for Content ID auditing loop (default: 300.0s).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SEC,
        help="Polling interval in seconds between YouTube API checks (default: 2.0s).",
    )
    parser.add_argument("--client-secrets", default=None, help="Path to client_secret.json.")
    parser.add_argument("--token-path", "--token-file", dest="token_path", default=None, help="Path to token.json.")
    parser.add_argument("--db-path", default="media_manifest.sqlite", help="Path to SQLite manifest database.")
    parser.add_argument("--project-id", default=None, help="Asset or Project ID for SQLite manifest tracking.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate upload and auditing workflow without live YouTube API network calls.",
    )
    return parser


def main() -> None:
    """CLI entry point for youtube_publisher.py."""
    parser = build_parser()
    args = parser.parse_args()

    publisher = YouTubePublisher(
        client_secrets_path=args.client_secrets,
        token_path=args.token_path,
        db_path=args.db_path,
        dry_run=args.dry_run,
    )

    result = publisher.publish_workflow(
        video_path=args.video,
        title=args.title,
        description=args.description,
        tags=args.tags,
        category_id=args.category_id,
        auto_promote=args.auto_promote and not args.skip_audit,
        poll_timeout_sec=args.poll_timeout,
        poll_interval_sec=args.poll_interval,
        project_id=args.project_id,
        db_path=args.db_path,
        seo_json_path=args.seo_json,
    )

    print("\n" + "=" * 70)
    print("YOUTUBE PUBLISH REPORT")
    print("=" * 70)
    print(f"Video ID:            {result.video_id}")
    print(f"Published URL:       {result.published_url}")
    print(f"Initial Privacy:     {result.initial_privacy}")
    print(f"Final Privacy:       {result.final_privacy}")
    print(f"Processing Status:   {result.processing_status}")
    print(f"Content ID Status:   {result.content_id_status}")
    print(f"Is Blocked:          {result.is_blocked}")
    if result.rejection_reason:
        print(f"Rejection Reason:    {result.rejection_reason}")
    if result.error_message:
        print(f"Error Message:       {result.error_message}")
    print("=" * 70)

    if result.is_blocked:
        sys.exit(2)
    elif result.error_message:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
