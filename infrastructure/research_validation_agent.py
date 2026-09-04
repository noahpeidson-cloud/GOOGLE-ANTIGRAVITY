"""
Main Research Validation Agent for Google Antigravity.
Implements the research validation, anti-canon empirical gate, and skill distillation architecture:
- Powered by Google Antigravity SDK & CuratedMemoryHub
- Validates external concepts against deterministic Python 3.13 / Windows test gates
- Offloads raw research payloads to D:\\AI_Platform\\research
- Distills verified workflows into production skills via workflow-skill-creator patterns
"""

import os
import sys
import json
import time
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Any, List, Optional

from infrastructure.workspace_context import WORKSPACE_ROOT
from infrastructure.curated_memory import CuratedMemoryHub, DEFAULT_DB_PATH

RESEARCH_DIR = Path(r"D:\AI_Platform\research")
SOURCES_DIR = RESEARCH_DIR / "sources"
CATALOG_FILE = RESEARCH_DIR / "notebook_catalog.json"
MATRIX_FILE = RESEARCH_DIR / "research_matrix.json"

CATEGORIES = {
    "harness_architecture": {
        "title": "Agent Harness Architecture & Outer-Loop Control",
        "keywords": ["harness", "outer-loop", "loop", "autodev", "rollback", "sandbox", "winder", "oracle", "puppygrap"]
    },
    "context_engineering": {
        "title": "Context Engineering, KV Caching & Token Economics",
        "keywords": ["kv cache", "prefix caching", "context", "prompt caching", "overhead", "token", "spheron", "galileo"]
    },
    "dual_ide_git": {
        "title": "Dual-IDE Coordination & Git Engineering",
        "keywords": ["claude", "git", "worktree", "integration", "antigravity ide", "branch", "willison", "eesel"]
    },
    "benchmarking_evals": {
        "title": "Empirical Benchmarking & SWE-bench Evals",
        "keywords": ["swe-bench", "benchmark", "gaia", "arena", "eval", "layer3labs", "chatbench", "lmsys"]
    },
    "media_engineering": {
        "title": "Media Engineering, 8K APV & EDM Pipelines",
        "keywords": ["video", "apv", "edm", "davinci", "audio", "lufs", "transcode", "short-form", "editing"]
    },
    "antigravity_internals": {
        "title": "Antigravity IDE Internals & Customizations",
        "keywords": ["mcp", "skill", "subagent", "gemini cli", "steering", "hook", "diagnostics", "sdk"]
    }
}

class ResearchValidationAgent:
    """Core autonomous research validation and anti-canon vetting agent."""

    def __init__(self, db_path: Optional[str] = None):
        self.workspace_root = WORKSPACE_ROOT
        self.memory_hub = CuratedMemoryHub(db_path)
        self.research_dir = RESEARCH_DIR
        self.sources_dir = SOURCES_DIR
        self._init_environment()

    def _init_environment(self):
        self.research_dir.mkdir(parents=True, exist_ok=True)
        self.sources_dir.mkdir(parents=True, exist_ok=True)
        for cat in CATEGORIES.keys():
            (self.sources_dir / cat).mkdir(parents=True, exist_ok=True)

    def categorize_source(self, title: str, content_preview: str = "") -> str:
        """Classify a research source into one of the 6 canonical architectural pillars."""
        text = (title + " " + content_preview).lower()
        scores = {}
        for cat, info in CATEGORIES.items():
            matches = sum(1 for kw in info["keywords"] if kw in text)
            scores[cat] = matches

        best_cat = max(scores, key=scores.get)
        if scores[best_cat] == 0:
            return "antigravity_internals"
        return best_cat

    def catalog_notebook_sources(self, raw_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Ingest raw sources from Gemini Notebook, categorize them, and save catalog to disk."""
        categorized_ledger = {cat: [] for cat in CATEGORIES.keys()}
        
        for src in raw_sources:
            src_id = src.get("id", "")
            title = src.get("title", "Untitled Source")
            cat = self.categorize_source(title)
            
            entry = {
                "id": src_id,
                "title": title,
                "category": cat,
                "category_title": CATEGORIES[cat]["title"],
                "status": "pending_validation",
                "ingested_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            categorized_ledger[cat].append(entry)

        catalog_data = {
            "notebook_id": "4b52cc67-9f81-4e85-a024-5f06756991ab",
            "total_sources": len(raw_sources),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "categories": categorized_ledger
        }

        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(catalog_data, f, indent=2)

        return catalog_data

    def run_empirical_gate(
        self,
        concept_name: str,
        hypothesis: str,
        domain_track: str,
        test_script_content: str,
        timeout_sec: int = 15
    ) -> Dict[str, Any]:
        """
        Execute a loud assertion test in an isolated runner.
        Ensures claims are never accepted subjectively without physical proof.
        """
        scratch_dir = Path(r"D:\AI_Platform\scratch\research_gates")
        scratch_dir.mkdir(parents=True, exist_ok=True)
        test_file = scratch_dir / f"gate_test_{int(time.time()*1000)}.py"
        test_file.write_text(test_script_content, encoding="utf-8")

        t0 = time.perf_counter()
        try:
            proc = subprocess.run(
                [sys.executable, str(test_file)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=str(self.workspace_root)
            )
            elapsed_ms = (time.perf_counter() - t0) * 1000
            passed = proc.returncode == 0
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
        except subprocess.TimeoutExpired:
            elapsed_ms = timeout_sec * 1000
            passed = False
            stdout = ""
            stderr = f"TIMEOUT: Test execution exceeded {timeout_sec}s"
        finally:
            try:
                test_file.unlink(missing_ok=True)
            except Exception:
                pass

        score = 10.0 if passed else 0.0
        if not passed:
            score = max(score, 1.0)

        result = {
            "concept_name": concept_name,
            "hypothesis": hypothesis,
            "domain_track": domain_track,
            "passed": passed,
            "score": round(score, 1),
            "elapsed_ms": round(elapsed_ms, 2),
            "stdout": stdout[:500],
            "stderr": stderr[:500],
            "status": "VALIDATED" if passed else "REJECTED",
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        # Update CuratedMemoryHub with empirical finding
        if passed:
            self.memory_hub.record(
                topic=concept_name,
                finding_summary=f"[VALIDATED] {hypothesis}. Gate test passed in {round(elapsed_ms, 1)}ms.",
                domain_track=domain_track,
                importance_score=9,
                evidence_source="research_validation_agent",
                metadata={"test_status": "passed", "elapsed_ms": round(elapsed_ms, 2)}
            )
        else:
            self.memory_hub.record(
                topic=concept_name,
                finding_summary=f"[CONTRADICTION] {hypothesis}. FAILED empirical test: {stderr[:150]}.",
                domain_track=domain_track,
                importance_score=8,
                evidence_source="research_validation_agent",
                metadata={"test_status": "failed", "error": stderr[:200]}
            )

        return result

    def distill_to_skill(
        self,
        skill_name: str,
        description: str,
        overview: str,
        workflow_steps: List[Dict[str, str]],
        example_invocations: List[str]
    ) -> Path:
        """
        Distill a validated research pattern into a canonical workspace skill
        adhering strictly to workflow-skill-creator standards (Rule 6).
        """
        skill_dir = self.workspace_root / ".agents" / "skills" / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"

        lines = [
            "---",
            f"name: {skill_name}",
            f"description: {description}",
            "---",
            "",
            f"# {skill_name.replace('-', ' ').title()} Skill",
            "",
            "## Overview",
            overview,
            "",
            "## Workflow",
            ""
        ]

        for idx, step in enumerate(workflow_steps, 1):
            lines.append(f"### {idx}. {step.get('title', f'Step {idx}')}")
            lines.append(step.get("instruction", ""))
            lines.append("")

        lines.extend([
            "## Natural Language Invocations",
            ""
        ])
        for inv in example_invocations:
            lines.append(f'- *"{inv}"*')
        lines.append("")

        content = "\n".join(lines)
        skill_md.write_text(content, encoding="utf-8")
        return skill_md

def main():
    print("[ResearchValidationAgent] Initializing agent on D:\\AI_Platform...")
    agent = ResearchValidationAgent()
    print("Agent ready. Workspace Root:", agent.workspace_root)
    print("Catalog Path:", CATALOG_FILE)

if __name__ == "__main__":
    main()
