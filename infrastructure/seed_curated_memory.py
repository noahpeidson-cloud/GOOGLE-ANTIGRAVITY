"""
Seed baseline architectural memory records into CuratedMemoryHub.
Drives grounding and counteracts recency bias across sessions.
"""

from infrastructure.curated_memory import CuratedMemoryHub

def seed_baseline_memory():
    hub = CuratedMemoryHub()
    
    records = [
        {
            "topic": "dual_loop_control_architecture",
            "domain_track": "platform",
            "importance_score": 10,
            "evidence_source": "NotebookLM: 4b52cc67-9f81-4e85-a024-5f06756991ab",
            "finding_summary": "Dual-loop architecture decouples agent reasoning: Fast Inner-Loop generates candidate actions, while Deterministic Outer-Loop executes test assertions, schema validation, and tool execution gates before accepting state transitions. Eliminates hallucinations and runaway speculative generation.",
            "metadata": {"type": "architecture", "verified": True}
        },
        {
            "topic": "storage_boundary_d_drive",
            "domain_track": "platform",
            "importance_score": 10,
            "evidence_source": "rules/05_zero_copy_storage.md & C: drive audit",
            "finding_summary": "All AI memory, vector stores, caches, models, and development workspaces are isolated on D: drive (D:\\GOOGLE ANTIGRAVITY, D:\\AI_Platform). C: drive is reserved strictly for OS operations. C: drive mirror caches must be pruned or junctioned.",
            "metadata": {"freed_gb_c_drive": 2.77, "root_path": "D:\\AI_Platform"}
        },
        {
            "topic": "context_health_prompt_caching",
            "domain_track": "platform",
            "importance_score": 9,
            "evidence_source": "NOOA Durable Memory Standard & NotebookLM MCP",
            "finding_summary": "To prevent context rot, maximize KV prefix caching, and avoid recency bias, prompt context must follow static-to-dynamic ordering: 1) System Rules, 2) Tool Schemas, 3) Curated Memory Dossiers, 4) Truncated History, 5) Volatile User Input. Large tool outputs must be offloaded to D: drive disk.",
            "metadata": {"cache_efficiency": "high", "offload_path": "D:\\AI_Platform\\cache"}
        },
        {
            "topic": "zero_discretion_red_phase",
            "domain_track": "platform",
            "importance_score": 10,
            "evidence_source": "Global Steering Directive R1 & rules/01_python_runtime.md",
            "finding_summary": "Agents must never self-certify success. Every feature or refactor must implement a Red Phase deterministic test with loud assertions that fails before implementation, and passes green before completion. Discretionary claims without physical test logs are strictly prohibited.",
            "metadata": {"policy": "R1", "framework": "pytest"}
        },
        {
            "topic": "audio_dsp_loudness_standard",
            "domain_track": "content_creation",
            "importance_score": 9,
            "evidence_source": "ffmpeg-audio-mastering skill & EBU R128 spec",
            "finding_summary": "All generated and ingested audio assets must pass EBU R128 two-pass loudness normalization targeting -14 LUFS integrated loudness with -1.0 dBFS true peak ceiling and 80Hz high-pass filtering.",
            "metadata": {"target_lufs": -14.0, "true_peak_dbfs": -1.0, "high_pass_hz": 80}
        },
        {
            "topic": "vertical_video_framing",
            "domain_track": "content_creation",
            "importance_score": 8,
            "evidence_source": "davinci-resolve-automation skill",
            "finding_summary": "9:16 vertical video production requires frame-accurate drop alignment, NVENC hardware encoding, and DaVinci Resolve Studio automation via fusionscript API.",
            "metadata": {"aspect_ratio": "9:16", "hardware_encoder": "nvenc"}
        },
        {
            "topic": "card_inventory_schema_integrity",
            "domain_track": "sports_cards",
            "importance_score": 8,
            "evidence_source": "card-valuation-hub skill & sports_cards/GEMINI.md",
            "finding_summary": "Card Ladder ETL pipelines must maintain 21-variable schema integrity in SQLite database card_inventory.db on D: drive, validating raw checklist parsing before upsert.",
            "metadata": {"db_name": "card_inventory.db", "schema_version": "21-var"}
        }
    ]
    
    seeded_ids = []
    for r in records:
        existing = hub.query(topic=r["topic"])
        if existing:
            rec_id = hub.record(
                topic=r["topic"],
                finding_summary=r["finding_summary"],
                domain_track=r["domain_track"],
                importance_score=r["importance_score"],
                evidence_source=r["evidence_source"],
                relationship_type="replaces",
                related_id=existing[0].id,
                metadata=r["metadata"]
            )
        else:
            rec_id = hub.record(
                topic=r["topic"],
                finding_summary=r["finding_summary"],
                domain_track=r["domain_track"],
                importance_score=r["importance_score"],
                evidence_source=r["evidence_source"],
                metadata=r["metadata"]
            )
        seeded_ids.append((r["topic"], rec_id))
    
    return seeded_ids

if __name__ == "__main__":
    results = seed_baseline_memory()
    print(f"Successfully seeded {len(results)} memory records:")
    for topic, rid in results:
        print(f"  - {topic}: {rid}")
