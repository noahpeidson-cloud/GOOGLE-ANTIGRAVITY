"""
Unit tests for client.py mocking transport layer and verifying error propagation.
Adheres to R2 Zero-Discretion Mandate and R38 Fail-Fast Guardrail.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from client import (
    MCPStdioClient,
    DirectClient,
    NotebookClientProtocol,
    NotebookClientError,
    NotebookClientConnectionError,
)


@pytest.mark.unit
@pytest.mark.mock
def test_client_protocol_interface():
    """Verify that both client implementations conform to NotebookClientProtocol."""
    assert issubclass(MCPStdioClient, NotebookClientProtocol), "LOUD FAILURE: MCPStdioClient must implement NotebookClientProtocol"
    assert issubclass(DirectClient, NotebookClientProtocol), "LOUD FAILURE: DirectClient must implement NotebookClientProtocol"


@pytest.mark.unit
@pytest.mark.mock
@pytest.mark.asyncio
async def test_mcp_stdio_client_get_notebook_success():
    """Verify MCPStdioClient calls 'notebook_get' and deserializes notebook details."""
    client = MCPStdioClient()
    mock_session = AsyncMock()
    mock_resp = MagicMock()
    
    mock_payload = {
        "status": "success",
        "notebook": {
            "id": "test-nb-id",
            "title": "Dual-Loop Control",
            "source_count": 2,
            "url": "https://notebooklm.google.com/notebook/test-nb-id",
        },
        "sources": [
            {"id": "src-1", "title": "Doc 1"},
            {"id": "src-2", "title": "Doc 2"},
        ],
    }
    mock_resp.content = [MagicMock(text=json.dumps(mock_payload))]
    mock_session.call_tool.return_value = mock_resp
    client._session = mock_session
    client._connected = True

    result = await client.get_notebook("test-nb-id")

    # Assert session.call_tool was called with exact arguments
    mock_session.call_tool.assert_awaited_once_with(
        "notebook_get",
        arguments={"notebook_id": "test-nb-id"}
    )
    assert result["notebook"]["id"] == "test-nb-id", "LOUD FAILURE: notebook id mismatch"
    assert len(result["sources"]) == 2, f"LOUD FAILURE: expected 2 sources, got {len(result['sources'])}"


@pytest.mark.unit
@pytest.mark.mock
@pytest.mark.asyncio
async def test_mcp_stdio_client_get_source_content_success():
    """Verify MCPStdioClient calls 'source_get_content' and returns content fields."""
    client = MCPStdioClient()
    mock_session = AsyncMock()
    mock_resp = MagicMock()

    mock_payload = {
        "status": "success",
        "content": "Full extracted document body text",
        "title": "Doc 1",
        "source_type": "unknown",
        "char_count": 33,
    }
    mock_resp.content = [MagicMock(text=json.dumps(mock_payload))]
    mock_session.call_tool.return_value = mock_resp
    client._session = mock_session
    client._connected = True

    res = await client.get_source_content("src-1")

    mock_session.call_tool.assert_awaited_once_with(
        "source_get_content",
        arguments={"source_id": "src-1"}
    )
    assert res["content"] == "Full extracted document body text", "LOUD FAILURE: content mismatch"
    assert res["char_count"] == 33, "LOUD FAILURE: char_count mismatch"


@pytest.mark.unit
@pytest.mark.mock
@pytest.mark.asyncio
async def test_mcp_stdio_client_get_notes_success():
    """Verify MCPStdioClient calls 'note' with action='list' and returns notes list."""
    client = MCPStdioClient()
    mock_session = AsyncMock()
    mock_resp = MagicMock()

    mock_payload = {
        "status": "success",
        "action": "list",
        "notebook_id": "test-nb-id",
        "notes": [
            {
                "id": "note-1",
                "title": "Synthesis Note",
                "content": "Full synthesis text...",
                "preview": "Full synthesis...",
            }
        ],
        "count": 1,
    }
    mock_resp.content = [MagicMock(text=json.dumps(mock_payload))]
    mock_session.call_tool.return_value = mock_resp
    client._session = mock_session
    client._connected = True

    notes = await client.get_notes("test-nb-id")

    mock_session.call_tool.assert_awaited_once_with(
        "note",
        arguments={"notebook_id": "test-nb-id", "action": "list"}
    )
    assert len(notes) == 1, f"LOUD FAILURE: expected 1 note, got {len(notes)}"
    assert notes[0]["id"] == "note-1", "LOUD FAILURE: note id mismatch"


@pytest.mark.unit
@pytest.mark.mock
@pytest.mark.asyncio
async def test_mcp_stdio_client_server_error_raises_loudly():
    """Verify R38 compliance: MCP tool error raises NotebookClientError instead of returning fake data."""
    client = MCPStdioClient()
    mock_session = AsyncMock()
    mock_resp = MagicMock()

    error_payload = {
        "status": "error",
        "error": "Notebook test-nb-id not found or access denied.",
    }
    mock_resp.content = [MagicMock(text=json.dumps(error_payload))]
    mock_session.call_tool.return_value = mock_resp
    client._session = mock_session
    client._connected = True

    with pytest.raises(NotebookClientError) as exc_info:
        await client.get_notebook("test-nb-id")

    assert "Notebook test-nb-id not found" in str(exc_info.value), (
        f"LOUD FAILURE: exception message did not contain error details: {exc_info.value}"
    )


@pytest.mark.unit
@pytest.mark.mock
@pytest.mark.asyncio
async def test_direct_client_delegation():
    """Verify DirectClient cleanly maps underlying service responses."""
    client = DirectClient()
    
    mock_nb_service = MagicMock()
    mock_nb_service.get_notebook.return_value = {
        "notebook_id": "direct-nb-id",
        "title": "Direct NB",
        "source_count": 1,
        "url": "https://example.com/direct-nb-id",
        "sources": [{"id": "s1", "title": "T1"}],
    }

    mock_sources_service = MagicMock()
    mock_sources_service.get_source_content.return_value = {
        "content": "Direct content",
        "title": "T1",
        "source_type": "web",
        "char_count": 14,
    }

    mock_notes_service = MagicMock()
    mock_notes_service.list_notes.return_value = {
        "notes": [{"id": "n1", "title": "N1", "content": "C1", "preview": "P1"}],
        "count": 1,
    }

    with patch("client.notebooks_service", mock_nb_service), \
         patch("client.sources_service", mock_sources_service), \
         patch("client.notes_service", mock_notes_service):
        
        client._raw_client = MagicMock()
        client._connected = True

        nb_res = await client.get_notebook("direct-nb-id")
        assert nb_res["notebook"]["id"] == "direct-nb-id", "LOUD FAILURE: id mismatch in DirectClient"
        assert len(nb_res["sources"]) == 1, "LOUD FAILURE: sources count mismatch in DirectClient"

        src_res = await client.get_source_content("s1")
        assert src_res["content"] == "Direct content", "LOUD FAILURE: source content mismatch in DirectClient"

        notes_res = await client.get_notes("direct-nb-id")
        assert len(notes_res) == 1, "LOUD FAILURE: notes count mismatch in DirectClient"
