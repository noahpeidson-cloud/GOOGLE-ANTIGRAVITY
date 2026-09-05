import sys
from pathlib import Path
sys.path.insert(0, r"d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor")

import json
import uuid
from schemas import NotebookExtractionPayload

payload_file = Path(r"d:\GOOGLE ANTIGRAVITY\content_creation\gemini_mcp_extractor\extracted_notebook_data.json")
assert payload_file.exists(), "File does not exist!"
size = payload_file.stat().st_size
print(f"File size: {size:,} bytes ({size / (1024*1024):.2f} MB)")

with open(payload_file, "r", encoding="utf-8") as f:
    raw_data = json.load(f)

# Pydantic schema validation
payload = NotebookExtractionPayload.model_validate(raw_data)
print("Pydantic schema validation: PASS (Payload valid against NotebookExtractionPayload)")

meta = payload.metadata
prov = payload.provenance
sources = payload.sources
notes = payload.notes

print(f"Metadata:")
print(f"  ID: {meta.id}")
print(f"  Title: '{meta.title}'")
print(f"  URL: {meta.url}")
print(f"  Source Count: {meta.source_count}")
print(f"  Emoji: {meta.emoji}")

print(f"Provenance:")
print(f"  Extracted At: {prov.extracted_at}")
print(f"  Extractor Version: {prov.extractor_version}")
print(f"  Transport: {prov.transport}")
print(f"  Is Dry Run: {prov.is_dry_run}")
print(f"  Limit Applied: {prov.limit_applied}")
print(f"  Total Sources: {prov.total_sources}")
print(f"  Successful Sources: {prov.successful_sources}")
print(f"  Failed Sources: {prov.failed_sources}")
print(f"  Total Notes: {prov.total_notes}")
print(f"  Duration: {prov.duration_seconds}s")

print(f"\nNotes Verification (Count: {len(notes)}):")
for i, n in enumerate(notes, 1):
    print(f"  Note #{i}: id={n.id}, title='{n.title}', chars={len(n.content)}")
    assert len(n.content.strip()) > 500, "Note content too short"

print(f"\nSources Verification (Count: {len(sources)}):")
failed = [s for s in sources if s.status != "success"]
empty = [s for s in sources if not s.content or len(s.content.strip()) == 0]
mismatches = [s for s in sources if s.char_count != len(s.content)]
invalid_uuids = []
for s in sources:
    try:
        uuid.UUID(s.id)
    except Exception:
        invalid_uuids.append(s.id)

total_chars = sum(len(s.content) for s in sources if s.content)

print(f"  Total Sources: {len(sources)}")
print(f"  Failed Sources: {len(failed)}")
print(f"  Empty Content Sources: {len(empty)}")
print(f"  Char Count Mismatches: {len(mismatches)}")
print(f"  Invalid UUIDs: {len(invalid_uuids)}")
print(f"  Total Extracted Characters: {total_chars:,}")
print(f"  First Source: '{sources[0].title}' (ID: {sources[0].id}, Chars: {len(sources[0].content):,})")
print(f"  Last Source: '{sources[-1].title}' (ID: {sources[-1].id}, Chars: {len(sources[-1].content):,})")

assert len(sources) == 61, f"Expected 61 sources, got {len(sources)}"
assert len(notes) == 1, f"Expected 1 note, got {len(notes)}"
assert len(failed) == 0, f"Expected 0 failed sources, got {len(failed)}"
assert len(empty) == 0, f"Expected 0 empty sources, got {len(empty)}"
assert len(mismatches) == 0, f"Expected 0 mismatches, got {len(mismatches)}"
assert len(invalid_uuids) == 0, f"Expected 0 invalid uuids, got {len(invalid_uuids)}"
assert total_chars > 2_000_000, f"Expected > 2M characters, got {total_chars}"

print("\nALL PAYLOAD INTEGRITY CHECKS PASSED EMPIRICALLY!")
