import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
import sys
from pathlib import Path
import json

# Add content_creation to sys.path
WORKSPACE_ROOT = Path(__file__).parent.parent
sys.path.append(str(WORKSPACE_ROOT))

from dashboard_backend import app, AssetStatus
from orchestrator import run_ingestion_phase
from metadata_tracker import MediaManifestDB

client = TestClient(app)

class TestMediaPipeline:
    
    @patch('google.genai.Client')
    def test_council_think_personas(self, mock_client_class):
        """
        TDAD: Asserts that /api/council_think returns exactly 5 EDM personas.
        """
        # Mock the Gemini API Response
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "dialogue": [
                {"persona": "The Retention Strategist", "thought": "Hook"},
                {"persona": "The Rhythm Editor", "thought": "Beat"},
                {"persona": "The Colorist", "thought": "Laser"},
                {"persona": "The Technical Lead", "thought": "9:16"},
                {"persona": "The Critic", "thought": "Vibe"}
            ],
            "synthetic_prompt": "Final prompt"
        })
        mock_client.models.generate_content.return_value = mock_response
        
        # Patch the actual call, but we also have to mock os.environ since backend checks it
        with patch.dict('os.environ', {'GEMINI_API_KEY': 'DUMMY_KEY'}):
            response = client.post("/api/council_think", json={"message": "Make it viral"})
            
        assert response.status_code == 200
        data = response.json()
        assert "dialogue" in data
        assert len(data["dialogue"]) == 5
        assert data["dialogue"][0]["persona"] == "The Retention Strategist"
        assert data["dialogue"][4]["persona"] == "The Critic"

    @patch('orchestrator.AssetIngestionRouter')
    @patch('orchestrator.FFmpegMasterProcessor')
    @patch('orchestrator.MediaManifestDB')
    def test_orchestrator_review_gate(self, mock_db_class, mock_processor_class, mock_router_class):
        """
        TDAD: Asserts that the orchestrator halts at Phase 1 (AWAITING_REVIEW)
        and does NOT trigger the render.
        """
        mock_db = MagicMock()
        mock_db_class.return_value = mock_db
        
        mock_router = MagicMock()
        mock_router_class.return_value = mock_router
        mock_router.ingest_asset.return_value = MagicMock(
            project_id="TEST_ASSET_123",
            canonical_filename="test_artist_test_track_v1.mp4",
            staged_path="d:/test/staged.mp4",
            raw_storage_path="d:/test/raw.mp4",
            probe_data=MagicMock(duration_seconds=100.0, is_hdr=False)
        )
        
        mock_processor = MagicMock()
        mock_processor_class.return_value = mock_processor
        
        run_ingestion_phase(
            input_file=Path("d:/test.mp4"),
            workspace_root=Path("d:/workspace"),
            event="test",
            artist="artist",
            track="track"
        )
        
        # Ensure that upsert_asset was called to set AWAITING_REVIEW
        calls = mock_db.upsert_asset.call_args_list
        statuses = [call.kwargs.get("current_status") for call in calls]
        
        assert AssetStatus.IN_PROGRESS in statuses
        assert AssetStatus.AWAITING_REVIEW in statuses
        # It should NOT go to APPROVED_FOR_RENDER
        assert AssetStatus.APPROVED_FOR_RENDER not in statuses

