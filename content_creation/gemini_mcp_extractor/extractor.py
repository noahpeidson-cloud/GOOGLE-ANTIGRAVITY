"""
CLI Entrypoint for Google NotebookLM bulk extraction.
Complies with R16 (absolute imports), R18 (dependency pre-flight), and R38 (fail-fast auth/data).
"""

import argparse
import asyncio
import logging
import os
from pathlib import Path
import sys
import time
from typing import List, Optional

# R16: Configure sys.path for absolute imports
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))


def verify_dependencies() -> None:
    """R18 Pre-Flight Dependency Guardrail: Verify all required modules are installed."""
    missing = []
    for pkg, import_name in [
        ("mcp", "mcp"),
        ("notebooklm-mcp-cli", "notebooklm_tools"),
        ("pydantic", "pydantic"),
        ("httpx", "httpx"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        sys.stderr.write(
            f"ERROR: Missing required dependencies: {', '.join(missing)}\n"
            f"Please run the pre-flight installation command:\n"
            f"    pip install -r requirements.txt\n"
        )
        sys.exit(1)


# Execute dependency pre-flight check immediately
verify_dependencies()

# R16: Absolute imports of local modules
import client
import schemas

logger = logging.getLogger("gemini_mcp_extractor")
DEFAULT_NOTEBOOK_ID = "4b52cc67-9f81-4e85-a024-5f06756991ab"


async def extract_source_worker(
    nb_client: client.NotebookClientProtocol,
    src_info: dict,
    semaphore: asyncio.Semaphore,
    index: int,
    total: int,
    fetch_content: bool = True,
    pacing_delay: float = 0.05,
    fail_fast: bool = False,
) -> schemas.ExtractedSource:
    """Fetch an individual source with semaphore concurrency control and error isolation."""
    src_id = src_info["id"]
    src_title = src_info.get("title", "Untitled Source")

    if not fetch_content:
        return schemas.ExtractedSource(
            id=src_id,
            title=src_title,
            status="skipped",
            content=None,
            char_count=0,
        )

    async with semaphore:
        sys.stdout.write(f"  [{index}/{total}] Fetching: {src_title[:60]}...\n")
        sys.stdout.flush()
        try:
            content_data = await nb_client.get_source_content(src_id)
            if pacing_delay > 0:
                await asyncio.sleep(pacing_delay)
            content_str = content_data.get("content", "")
            return schemas.ExtractedSource(
                id=src_id,
                title=src_title,
                source_type=content_data.get("source_type", "unknown"),
                char_count=content_data.get("char_count", len(content_str)),
                content=content_str,
                status="success",
            )
        except Exception as e:
            logger.warning(f"Failed to fetch source {src_id} ('{src_title}'): {e}")
            if fail_fast:
                raise client.FatalSourceExtractionError(
                    f"Aborting on source failure '{src_title}' ({src_id}): {e}"
                ) from e
            # R38 Compliance: DO NOT generate mock/fallback text!
            return schemas.ExtractedSource(
                id=src_id,
                title=src_title,
                status="failed",
                error=str(e),
                content=None,
                char_count=0,
            )


async def run_extraction(
    notebook_id: str,
    output_path: Optional[Path] = None,
    transport: str = "mcp",
    dry_run: bool = False,
    limit: Optional[int] = None,
    concurrency: int = 4,
    fetch_content: bool = True,
    output_format: str = "json",
    fail_fast: bool = False,
) -> schemas.NotebookExtractionPayload:
    """Main async pipeline executing end-to-end extraction."""
    start_time = time.perf_counter()

    if output_path is None:
        default_filename = "extracted_notebook_data_dryrun.json" if dry_run else "extracted_notebook_data.json"
        output_path = Path(default_filename).resolve()
    else:
        output_path = Path(output_path).resolve()

    effective_limit = limit
    if dry_run:
        effective_limit = 2 if (limit is None or limit > 2) else limit
        print(f"=== DRY-RUN MODE: Extracting max {effective_limit} source(s) + all notes ===")

    # R38: Validate authentication before connecting
    client.require_authentication()

    nb_client = client.create_client(transport=transport)
    async with nb_client:
        # 1. Fetch Notebook Metadata
        print(f"Connecting to NotebookLM via '{transport}' transport...")
        print(f"Fetching notebook metadata for ID: {notebook_id}...")
        nb_dict = await nb_client.get_notebook(notebook_id)

        metadata = schemas.NotebookMetadata(
            id=nb_dict["id"],
            title=nb_dict["title"],
            url=nb_dict["url"],
            source_count=nb_dict["source_count"],
            emoji=nb_dict.get("emoji"),
        )
        print(f"Target: \"{metadata.title}\" | Reported Sources: {metadata.source_count}")

        # 2. Fetch Notes
        print("Fetching notebook notes...")
        raw_notes = await nb_client.get_notes(notebook_id)
        notes = [
            schemas.ExtractedNote(
                id=n["id"],
                title=n.get("title", "Untitled Note"),
                content=n.get("content", ""),
                preview=n.get("preview"),
            )
            for n in raw_notes
        ]
        print(f"Successfully retrieved {len(notes)} note(s).")

        # 3. Fetch Sources
        raw_sources = nb_dict.get("sources", [])
        if effective_limit and effective_limit > 0:
            raw_sources = raw_sources[:effective_limit]

        total_sources = len(raw_sources)
        print(f"Processing {total_sources} source(s) with concurrency={concurrency}...")

        semaphore = asyncio.Semaphore(concurrency)
        tasks = [
            extract_source_worker(
                nb_client=nb_client,
                src_info=src,
                semaphore=semaphore,
                index=i,
                total=total_sources,
                fetch_content=fetch_content,
                fail_fast=fail_fast,
            )
            for i, src in enumerate(raw_sources, 1)
        ]
        extracted_sources = await asyncio.gather(*tasks)

    # 4. Construct Payload & Provenance
    duration = round(time.perf_counter() - start_time, 2)
    successful_count = sum(1 for s in extracted_sources if s.status == "success")
    failed_count = sum(1 for s in extracted_sources if s.status == "failed")

    provenance = schemas.ExtractionProvenance(
        transport=transport,
        total_sources=len(extracted_sources),
        successful_sources=successful_count,
        failed_sources=failed_count,
        total_notes=len(notes),
        is_dry_run=dry_run,
        limit_applied=effective_limit,
        duration_seconds=duration,
    )

    payload = schemas.NotebookExtractionPayload(
        metadata=metadata,
        sources=extracted_sources,
        notes=notes,
        provenance=provenance,
    )

    # 5. Atomic File Output
    saved_file = payload.save(output_path, format=output_format)
    file_size_kb = round(saved_file.stat().st_size / 1024, 2)

    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)
    print(f"Notebook Title:       {metadata.title}")
    print(f"Notebook UUID:        {metadata.id}")
    print(f"Transport Used:       {transport}")
    print(f"Notes Extracted:      {len(notes)}")
    print(f"Sources Processed:    {len(extracted_sources)} (Success: {successful_count}, Failed: {failed_count})")
    print(f"Total Duration:       {duration} seconds")
    print(f"Output File:          {saved_file} ({file_size_kb} KB)")
    print(f"Output Format:        {output_format.upper()}")
    print("=" * 60 + "\n")

    return payload


def build_parser() -> argparse.ArgumentParser:
    """Build and configure the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Gemini Notebook MCP Extractor: Bulk extract sources and notes from Google NotebookLM."
    )
    parser.add_argument(
        "--notebook-id",
        type=str,
        default=DEFAULT_NOTEBOOK_ID,
        help=f"Target notebook UUID (default: {DEFAULT_NOTEBOOK_ID})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default=None,
        help="Target output file path (default: extracted_notebook_data.json, or extracted_notebook_data_dryrun.json if --dry-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode: extracts a fast subset (max 2 sources) and all notes.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of sources to extract (default: all).",
    )
    parser.add_argument(
        "--transport",
        choices=["mcp", "direct"],
        default="mcp",
        help="Transport protocol: 'mcp' (stdio JSON-RPC subprocess) or 'direct' (in-process services). Default: mcp",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=4,
        help="Maximum concurrent source content fetches (default: 4).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "jsonl"],
        default="json",
        help="Serialization format: 'json' (indented) or 'jsonl' (line-delimited). Default: json",
    )
    parser.add_argument(
        "--no-content",
        action="store_true",
        help="Fetch source metadata only without downloading full text.",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Immediately abort execution on any single source fetch failure (R38).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable detailed debug logging.",
    )
    return parser


def main() -> None:
    """Main CLI execution entrypoint."""
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except AttributeError:
            pass

    parser = build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if args.output:
        output_path = Path(args.output).resolve()
    else:
        default_filename = "extracted_notebook_data_dryrun.json" if args.dry_run else "extracted_notebook_data.json"
        output_path = Path(default_filename).resolve()

    try:
        asyncio.run(
            run_extraction(
                notebook_id=args.notebook_id,
                output_path=output_path,
                transport=args.transport,
                dry_run=args.dry_run,
                limit=args.limit,
                concurrency=args.concurrency,
                fetch_content=not args.no_content,
                output_format=args.format,
                fail_fast=args.fail_fast,
            )
        )
    except client.AuthenticationError as e:
        sys.stderr.write(f"\n{e}\n")
        sys.exit(1)
    except client.NotebookNotFoundError as e:
        sys.stderr.write(f"\nERROR: {e}\n")
        sys.exit(1)
    except KeyboardInterrupt:
        sys.stderr.write("\nExtraction interrupted by user.\n")
        sys.exit(130)
    except Exception as e:
        sys.stderr.write(f"\nFATAL EXTRACTION ERROR: {e}\n")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(3)


if __name__ == "__main__":
    main()
