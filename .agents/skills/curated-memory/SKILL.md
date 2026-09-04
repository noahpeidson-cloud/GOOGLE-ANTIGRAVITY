---
name: curated-memory
description: Operational runbook for managing the NOOA Curated Memory Hub and running the full-system empirical benchmark harness.
---

# Curated Memory & Benchmark Governance Skill

## Overview
This skill provides deterministic commands to query, seed, supersede, and benchmark durable cross-session knowledge for Google Antigravity and AI Platform.

## 1. Querying Curated Knowledge Dossiers
To retrieve high-importance domain findings without bloating prompt context:

```python
from infrastructure.curated_memory import CuratedMemoryHub
hub = CuratedMemoryHub()

# Retrieve active knowledge for a specific domain track
print(hub.get_dossier("platform"))
print(hub.get_dossier("content_creation"))
print(hub.get_dossier("sports_cards"))
```

## 2. Recording & Superseding Knowledge
To record a new architectural discovery or supersede outdated facts:

```python
# Supersede an older record with newer evidence
new_id = hub.record(
    topic="audio_dsp_loudness_standard",
    finding_summary="All ingested audio must pass EBU R128 normalization targeting -14 LUFS.",
    domain_track="content_creation",
    importance_score=9,
    evidence_source="ffmpeg-audio-mastering skill",
    relationship_type="replaces",
    related_id=old_record_id
)
```

## 3. Running the Empirical Benchmark Harness
To verify all 5 ecosystem pillars (Rules, Memory, Skills, Subagents, Storage) and confirm a 10.0/10 health score:

```powershell
python -m infrastructure.benchmark_harness
```

## Usage
1. Inspect active domain knowledge using `hub.get_dossier(<domain>)`.
2. When architectural decisions or refactors occur, record them in the database with explicit importance scores.
3. If an old approach is deprecated or replaced, link the new record with `relationship_type="replaces"` to maintain a clean knowledge graph.

## Examples
- **Example 1: Platform Dossier Lookup**: Query `hub.get_dossier('platform')` before architectural changes to verify storage boundaries and prompt caching standards.
- **Example 2: Media DSP Update**: Record an updated LUFS threshold using `relationship_type='replaces'` to automatically supersede legacy records.

## Natural Language Invocations
- *"Query the curated memory dossier for the platform track"*
- *"Record this architectural decision into curated memory"*
- *"Run the full-system empirical benchmark harness"*
