"""
Dual transport client adapters for Google NotebookLM extraction.
Supports both MCP stdio transport (JSON-RPC over subprocess) and direct in-process service calls.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

# Module-level imports of services for DirectClient and patching in tests
from notebooklm_tools.services import (
    notebooks as notebooks_service,
    notes as notes_service,
    sources as sources_service,
)

logger = logging.getLogger(__name__)


class NotebookExtractionError(Exception):
    """Base exception for all notebook extraction errors."""
    pass


NotebookClientError = NotebookExtractionError
ExtractionError = NotebookExtractionError


class AuthenticationError(NotebookExtractionError):
    """Raised when NotebookLM authentication credentials are missing or expired."""
    pass


AuthValidationError = AuthenticationError


class ToolCallError(NotebookExtractionError):
    """Raised when an MCP tool call returns an error status or malformed response."""
    pass


ToolExecutionError = ToolCallError


class NotebookClientConnectionError(NotebookExtractionError):
    """Raised when client fails to connect or transport fails."""
    pass


TransportError = NotebookClientConnectionError


class NotebookNotFoundError(NotebookExtractionError):
    """Raised when a requested notebook UUID cannot be found or accessed."""
    pass


class FatalSourceExtractionError(NotebookExtractionError):
    """Raised when source extraction fails under --fail-fast policy."""
    pass


@runtime_checkable
class NotebookClientProtocol(Protocol):
    """Unified asynchronous protocol for notebook extraction clients."""

    async def connect(self) -> None:
        """Establish connection or initialize client resources."""
        ...

    async def disconnect(self) -> None:
        """Terminate connection or cleanup resources."""
        ...

    async def get_notebook(self, notebook_id: str) -> Dict[str, Any]:
        """
        Retrieve notebook metadata and list of source records.
        Returns:
            {
                "id": str,
                "title": str,
                "source_count": int,
                "url": str,
                "emoji": Optional[str],
                "sources": List[{"id": str, "title": str}],
                "notebook": Dict[str, Any]
            }
        """
        ...

    async def get_notes(self, notebook_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all notes for the notebook.
        Returns:
            List[{"id": str, "title": str, "content": str, "preview": Optional[str]}]
        """
        ...

    async def get_source_content(self, source_id: str) -> Dict[str, Any]:
        """
        Retrieve raw text content for an individual source document.
        Returns:
            {"id": str, "title": str, "content": str, "source_type": str, "char_count": int}
        """
        ...

    async def __aenter__(self) -> "NotebookClientProtocol":
        ...

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        ...


def check_cached_authentication(profile: Optional[str] = None) -> bool:
    """Verify if cached NotebookLM authentication credentials exist on disk or env."""
    if os.environ.get("NOTEBOOKLM_COOKIES"):
        return True
    try:
        from notebooklm_tools.core.auth import load_cached_tokens
        tokens = load_cached_tokens(profile_name=profile)
        if tokens is None:
            return False
        if hasattr(tokens, "is_expired") and tokens.is_expired():
            return False
        return bool(getattr(tokens, "cookies", None))
    except Exception as e:
        logger.debug(f"Auth check failed with exception: {e}")
        return False


def require_authentication(profile: Optional[str] = None) -> None:
    """
    Fail-fast authentication check (R38).
    Raises AuthenticationError with explicit remediation instructions if tokens are missing.
    """
    if not check_cached_authentication(profile=profile):
        error_banner = (
            "\n" + "=" * 78 + "\n"
            "[FATAL AUTH ERROR] Google NotebookLM Authentication Required\n"
            "=" * 78 + "\n"
            "No active NotebookLM authentication tokens found on disk.\n"
            "Checked locations:\n"
            "  1. Environment variable: NOTEBOOKLM_COOKIES\n"
            "  2. Profile cache:       ~/.notebooklm-mcp-cli/profiles/default/cookies.json\n\n"
            "REMEDIATION:\n"
            "  Run 'nlm login' in your terminal to authenticate via Google Chrome.\n"
            "  Once authenticated, re-run this extraction script.\n"
            + "=" * 78 + "\n"
        )
        sys.stderr.write(error_banner)
        sys.stderr.flush()
        raise AuthenticationError(
            "CRITICAL: No active NotebookLM authentication tokens found on disk.\n"
            "Remediation: Run 'nlm login' to authenticate via Chrome CDP."
        )


class MCPStdioClient:
    """
    Client adapter connecting to the 'gemini-notebook' MCP server over stdio JSON-RPC.
    Spawns 'python -m notebooklm_tools.mcp.server' using the active Python executable.
    """

    def __init__(
        self,
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        env: Optional[Dict[str, str]] = None,
        timeout: float = 60.0,
    ):
        self.command = command or sys.executable
        self.args = args or ["-m", "notebooklm_tools.mcp.server"]
        self.env = env
        self.timeout = timeout
        self._read = None
        self._write = None
        self._session = None
        self._stdio_cm = None
        self._session_cm = None
        self._connected = False

    async def connect(self) -> None:
        """Spawn the MCP server process and perform JSON-RPC handshake."""
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        require_authentication()

        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env,
        )

        logger.debug(f"Connecting to MCP server: {self.command} {' '.join(self.args)}")
        try:
            self._stdio_cm = stdio_client(server_params)
            self._read, self._write = await self._stdio_cm.__aenter__()

            self._session_cm = ClientSession(self._read, self._write)
            self._session = await self._session_cm.__aenter__()
            await self._session.initialize()
            self._connected = True
            logger.debug("MCP Stdio Client initialized successfully.")
        except Exception as e:
            self._connected = False
            raise NotebookClientConnectionError(f"Failed to connect to MCP stdio server: {e}") from e

    async def disconnect(self) -> None:
        """Close MCP session and terminate subprocess."""
        self._connected = False
        if self._session_cm:
            try:
                await self._session_cm.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error exiting MCP session: {e}")
            self._session = None
            self._session_cm = None

        if self._stdio_cm:
            try:
                await self._stdio_cm.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"Error exiting stdio context: {e}")
            self._read = None
            self._write = None
            self._stdio_cm = None

    async def __aenter__(self) -> "MCPStdioClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    def _ensure_connected(self) -> None:
        if not self._connected and not self._session:
            raise ToolCallError("Client is not connected. Call 'await client.connect()' first.")

    async def get_notebook(self, notebook_id: str) -> Dict[str, Any]:
        self._ensure_connected()
        try:
            res = await asyncio.wait_for(
                self._session.call_tool("notebook_get", arguments={"notebook_id": notebook_id}),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            raise ToolCallError(f"Timed out after {self.timeout}s calling 'notebook_get' for {notebook_id}")
        except Exception as e:
            raise ToolCallError(f"Failed to call 'notebook_get': {e}") from e

        if not res.content:
            raise ToolCallError("Empty response returned from 'notebook_get'")

        data = json.loads(res.content[0].text)
        if isinstance(data, dict) and data.get("status") == "error":
            err_msg = data.get("error", "Unknown error")
            if "not found" in err_msg.lower() or "not_found" in err_msg.lower() or "code 5" in err_msg.lower():
                raise NotebookNotFoundError(f"Notebook '{notebook_id}' not found: {err_msg}")
            if "unauthenticated" in err_msg.lower() or "code 16" in err_msg.lower():
                raise AuthenticationError(f"Session expired: {err_msg}. Run 'nlm login'.")
            raise ToolCallError(f"MCP 'notebook_get' error: {err_msg}")

        nb = data.get("notebook", {})
        nb_id = nb.get("id") or notebook_id
        title = nb.get("title", "")
        source_count = nb.get("source_count", len(data.get("sources", [])))
        url = nb.get("url", "")
        emoji = nb.get("emoji")
        sources = data.get("sources", [])

        nb_info = {
            "id": nb_id,
            "title": title,
            "source_count": source_count,
            "url": url,
            "emoji": emoji,
        }
        return {
            "id": nb_id,
            "title": title,
            "source_count": source_count,
            "url": url,
            "emoji": emoji,
            "sources": sources,
            "notebook": nb_info,
        }

    async def get_notes(self, notebook_id: str) -> List[Dict[str, Any]]:
        self._ensure_connected()
        try:
            res = await asyncio.wait_for(
                self._session.call_tool("note", arguments={"notebook_id": notebook_id, "action": "list"}),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            raise ToolCallError(f"Timed out after {self.timeout}s calling 'note' for {notebook_id}")
        except Exception as e:
            raise ToolCallError(f"Failed to call 'note': {e}") from e

        if not res.content:
            return []

        data = json.loads(res.content[0].text)
        if isinstance(data, dict) and data.get("status") == "error":
            raise ToolCallError(f"MCP 'note' error: {data.get('error')}")

        return data.get("notes", [])

    async def get_source_content(self, source_id: str) -> Dict[str, Any]:
        self._ensure_connected()
        try:
            res = await asyncio.wait_for(
                self._session.call_tool("source_get_content", arguments={"source_id": source_id}),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            raise ToolCallError(f"Timed out after {self.timeout}s calling 'source_get_content' for {source_id}")
        except Exception as e:
            raise ToolCallError(f"Failed to call 'source_get_content': {e}") from e

        if not res.content:
            raise ToolCallError(f"Empty content returned for source {source_id}")

        data = json.loads(res.content[0].text)
        if isinstance(data, dict) and data.get("status") == "error":
            raise ToolCallError(f"Source content error: {data.get('error')}")

        content_str = data.get("content", "")
        return {
            "id": source_id,
            "title": data.get("title", ""),
            "content": content_str,
            "source_type": data.get("source_type", "unknown"),
            "char_count": data.get("char_count", len(content_str)),
        }


class DirectClient:
    """
    Direct in-process service client adapter.
    Bypasses subprocess stdio by calling 'notebooklm_tools.services' directly in a thread pool.
    """

    def __init__(self, profile: Optional[str] = None, timeout: float = 60.0):
        self.profile = profile
        self.timeout = timeout
        self._client = None
        self._raw_client = None
        self._connected = False

    async def connect(self) -> None:
        """Initialize authenticated client in background thread."""
        require_authentication(profile=self.profile)
        from notebooklm_tools.mcp.tools._utils import get_client
        if self.profile:
            from notebooklm_tools.core.auth import load_cached_tokens
            from notebooklm_tools.core.client import NotebookLMClient
            tokens = load_cached_tokens(profile_name=self.profile)
            if not tokens:
                raise AuthenticationError(f"Profile '{self.profile}' has no valid tokens.")
            self._client = NotebookLMClient(
                cookies=tokens.cookies,
                csrf_token=tokens.csrf_token,
                session_id=tokens.session_id,
                build_label=tokens.build_label or "",
                base_host=tokens.base_host or "",
            )
        else:
            self._client = await asyncio.to_thread(get_client)
        self._raw_client = self._client
        self._connected = True
        logger.debug("Direct Service Client initialized successfully.")

    async def disconnect(self) -> None:
        """Release direct client resources."""
        self._connected = False
        if self._client and hasattr(self._client, "close"):
            await asyncio.to_thread(self._client.close)
        self._client = None
        self._raw_client = None

    async def __aenter__(self) -> "DirectClient":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.disconnect()

    def _ensure_connected(self) -> Any:
        client_obj = self._raw_client or self._client
        if not self._connected and not client_obj:
            raise ToolCallError("Client is not connected. Call 'await client.connect()' first.")
        return client_obj

    async def get_notebook(self, notebook_id: str) -> Dict[str, Any]:
        client_obj = self._ensure_connected()
        try:
            res = await asyncio.to_thread(notebooks_service.get_notebook, client_obj, notebook_id)
            nb_id = res.get("notebook_id") or res.get("id") or notebook_id
            title = res.get("title", "")
            source_count = res.get("source_count", len(res.get("sources", [])))
            url = res.get("url", "")
            emoji = res.get("emoji")
            sources = res.get("sources", [])
            nb_info = {
                "id": nb_id,
                "title": title,
                "source_count": source_count,
                "url": url,
                "emoji": emoji,
            }
            return {
                "id": nb_id,
                "title": title,
                "source_count": source_count,
                "url": url,
                "emoji": emoji,
                "sources": sources,
                "notebook": nb_info,
            }
        except Exception as e:
            err_msg = str(e)
            if "not found" in err_msg.lower() or "not_found" in err_msg.lower() or "code 5" in err_msg.lower():
                raise NotebookNotFoundError(f"Notebook '{notebook_id}' not found: {err_msg}")
            if "unauthenticated" in err_msg.lower() or "code 16" in err_msg.lower():
                raise AuthenticationError(f"Session expired: {err_msg}. Run 'nlm login'.")
            raise ToolCallError(f"Direct get_notebook error: {err_msg}") from e

    async def get_notes(self, notebook_id: str) -> List[Dict[str, Any]]:
        client_obj = self._ensure_connected()
        try:
            res = await asyncio.to_thread(notes_service.list_notes, client_obj, notebook_id)
            return res.get("notes", [])
        except Exception as e:
            raise ToolCallError(f"Direct list_notes error: {e}") from e

    async def get_source_content(self, source_id: str) -> Dict[str, Any]:
        client_obj = self._ensure_connected()
        try:
            res = await asyncio.to_thread(sources_service.get_source_content, client_obj, source_id)
            content_str = res.get("content", "")
            return {
                "id": source_id,
                "title": res.get("title", ""),
                "content": content_str,
                "source_type": res.get("source_type", "unknown"),
                "char_count": res.get("char_count", len(content_str)),
            }
        except Exception as e:
            raise ToolCallError(f"Direct get_source_content error: {e}") from e


def create_client(transport: str = "mcp", **kwargs) -> NotebookClientProtocol:
    """
    Factory function to instantiate the selected client adapter.
    Args:
        transport: 'mcp' (default stdio transport) or 'direct' (in-process service)
    """
    t = transport.lower().strip()
    if t == "mcp":
        return MCPStdioClient(**kwargs)
    elif t == "direct":
        return DirectClient(**kwargs)
    else:
        raise ValueError(f"Invalid transport '{transport}'. Must be 'mcp' or 'direct'.")
