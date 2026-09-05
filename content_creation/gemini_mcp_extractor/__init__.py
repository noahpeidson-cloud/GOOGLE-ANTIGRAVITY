"""
Gemini MCP Extractor Package.
"""

try:
    from .schemas import (
        ExtractedNote,
        ExtractedSource,
        ExtractionProvenance,
        NotebookExtractionPayload,
        NotebookMetadata,
    )
    from .client import (
        AuthenticationError,
        DirectClient,
        MCPStdioClient,
        NotebookClientProtocol,
        NotebookExtractionError,
        create_client,
    )
except ImportError:
    from schemas import (
        ExtractedNote,
        ExtractedSource,
        ExtractionProvenance,
        NotebookExtractionPayload,
        NotebookMetadata,
    )
    from client import (
        AuthenticationError,
        DirectClient,
        MCPStdioClient,
        NotebookClientProtocol,
        NotebookExtractionError,
        create_client,
    )

__all__ = [
    "NotebookMetadata",
    "ExtractedSource",
    "ExtractedNote",
    "ExtractionProvenance",
    "NotebookExtractionPayload",
    "NotebookClientProtocol",
    "MCPStdioClient",
    "DirectClient",
    "NotebookExtractionError",
    "AuthenticationError",
    "create_client",
]
