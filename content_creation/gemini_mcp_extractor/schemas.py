"""
Data contracts and Pydantic v2 schemas for Gemini Notebook extraction.
Provides strict validation, serialization, and JSON/JSONL output generation.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION = "1.0.0"
EXTRACTOR_VERSION = "1.0.0"


class NotebookMetadata(BaseModel):
    """Metadata describing a Google NotebookLM notebook."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique UUID of the notebook")
    title: str = Field(..., description="Display title of the notebook")
    url: str = Field(..., description="Canonical web URL of the notebook")
    source_count: int = Field(..., description="Total number of indexed sources in the notebook")
    emoji: Optional[str] = Field(default=None, description="Optional emoji icon assigned to the notebook")


class ExtractedSource(BaseModel):
    """Normalized representation of an extracted source document."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique UUID of the source document")
    title: str = Field(..., description="Title or filename of the source document")
    source_type: str = Field(default="unknown", description="Type of source (web, file, text, youtube, unknown)")
    url: Optional[str] = Field(default=None, description="Original source URL if applicable")
    char_count: int = Field(default=0, description="Character count of the raw extracted text")
    content: Optional[str] = Field(default=None, description="Full unedited text content of the source")
    status: str = Field(default="success", description="Extraction status: 'success', 'failed', or 'skipped'")
    error: Optional[str] = Field(default=None, description="Error message if extraction failed")


class ExtractedNote(BaseModel):
    """User note or research synthesis within a notebook."""
    model_config = ConfigDict(extra="ignore")

    id: str = Field(..., description="Unique UUID of the note")
    title: str = Field(..., description="Title of the note")
    content: str = Field(default="", description="Full markdown content of the note")
    preview: Optional[str] = Field(default=None, description="Short preview snippet of the note")


class ExtractionProvenance(BaseModel):
    """Execution metadata and audit provenance for an extraction run."""
    model_config = ConfigDict(extra="ignore")

    extracted_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of extraction",
    )
    extractor_version: str = Field(default=EXTRACTOR_VERSION, description="Version of the extraction engine")
    transport: str = Field(..., description="Transport mechanism used: 'mcp' or 'direct'")
    total_sources: int = Field(..., description="Total sources processed in payload")
    successful_sources: int = Field(default=0, description="Count of sources successfully retrieved")
    failed_sources: int = Field(default=0, description="Count of sources that failed retrieval")
    total_notes: int = Field(..., description="Total notes extracted in payload")
    is_dry_run: bool = Field(default=False, description="Flag indicating whether run was a dry run")
    limit_applied: Optional[int] = Field(default=None, description="Source limit applied during execution")
    duration_seconds: Optional[float] = Field(default=None, description="Elapsed execution time in seconds")


class NotebookExtractionPayload(BaseModel):
    """Top-level unified schema representing a complete extracted notebook."""
    model_config = ConfigDict(extra="ignore")

    schema_version: str = Field(default=SCHEMA_VERSION, description="Payload schema specification version")
    metadata: NotebookMetadata = Field(..., description="Notebook overview metadata")
    sources: List[ExtractedSource] = Field(default_factory=list, description="List of all extracted sources")
    notes: List[ExtractedNote] = Field(default_factory=list, description="List of all extracted notes")
    provenance: ExtractionProvenance = Field(..., description="Execution provenance and audit trail")

    def to_json(self, indent: int = 2) -> str:
        """Serialize payload to indented JSON string."""
        return self.model_dump_json(indent=indent)

    def to_jsonl(self) -> str:
        """Serialize payload to JSON Lines format (one JSON object per line: provenance, metadata, notes, sources)."""
        lines = [
            json.dumps({"type": "provenance", "data": self.provenance.model_dump()}, ensure_ascii=False),
            json.dumps({"type": "metadata", "data": self.metadata.model_dump()}, ensure_ascii=False),
        ]
        for note in self.notes:
            lines.append(json.dumps({"type": "note", "data": note.model_dump()}, ensure_ascii=False))
        for source in self.sources:
            lines.append(json.dumps({"type": "source", "data": source.model_dump()}, ensure_ascii=False))
        return "\n".join(lines) + "\n"

    def save(self, filepath: Path | str, format: str = "json") -> Path:
        """
        Atomically save payload to disk with UTF-8 encoding.
        Supports format='json' (default) and format='jsonl'.
        Ensures same-filesystem tempfile creation, fsync, and atomic os.replace.
        """
        path = Path(filepath).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        content = self.to_jsonl() if format.lower() == "jsonl" else self.to_json(indent=2)

        temp_file_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=path.parent,
                delete=False,
                suffix=".tmp",
                prefix=f".{path.name}.",
                encoding="utf-8",
                newline="\n",
            ) as tf:
                temp_file_path = Path(tf.name)
                tf.write(content)
                tf.flush()
                os.fsync(tf.fileno())

            # File handle closed; perform atomic replacement
            os.replace(temp_file_path, path)
            temp_file_path = None
        finally:
            if temp_file_path is not None and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                except OSError:
                    pass

        return path
