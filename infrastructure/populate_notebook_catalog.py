"""
Populates the Notebook Catalog on D:\\AI_Platform from the Gemini Notebook MCP export.
Categorizes all 61 sources without treating them as canon.
"""

import json
from pathlib import Path
from infrastructure.research_validation_agent import ResearchValidationAgent

MCP_OUTPUT = Path(r"C:\Users\noahp\.gemini\antigravity\brain\e7927e32-daf3-46a7-bb8d-30024676c29f\.system_generated\steps\699\output.txt")

def populate_catalog():
    if not MCP_OUTPUT.exists():
        raise FileNotFoundError(f"MCP output file not found at {MCP_OUTPUT}")

    with open(MCP_OUTPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    sources = data.get("sources", [])
    print(f"Loaded {len(sources)} sources from Gemini Notebook export.")

    agent = ResearchValidationAgent()
    catalog = agent.catalog_notebook_sources(sources)

    print("\nCategorical Breakdown:")
    for cat, items in catalog["categories"].items():
        print(f"  - {cat}: {len(items)} sources")

    return catalog

if __name__ == "__main__":
    populate_catalog()
