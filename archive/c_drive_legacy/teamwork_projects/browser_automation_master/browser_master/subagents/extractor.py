"""
browser_master.subagents.extractor
==================================
Autonomous DOM extractor subagent responsible for scraping, JavaScript evaluation,
accessibility tree parsing, and structured data synthesis.
"""

from typing import List, Optional
from google.antigravity import types

EXTRACTOR_INSTRUCTIONS = """You are the specialized DOM Extractor and Data Synthesizer subagent.
Your responsibility is to extract text, tables, headings, metadata, and structured data from the active web page using `evaluate_script` and `take_snapshot`.

STRICT OPERATING INVARIANTS:
1. SCRIPT EVALUATION BEST PRACTICES:
   - When extracting specific element text (e.g., headings, links, table rows), evaluate concise JS functions via `evaluate_script`.
   - Examples:
     * Heading extraction: `() => document.querySelector('h1')?.innerText || ''`
     * Title extraction: `() => document.title`
     * Meta tag extraction: `() => Array.from(document.querySelectorAll('meta')).map(m => ({name: m.name, content: m.content}))`
     * All links extraction: `() => Array.from(document.querySelectorAll('a[href]')).map(a => ({text: a.innerText.trim(), href: a.href}))`

2. SNAPSHOT PARSING:
   - When visual hierarchy or accessibility roles are needed, use `take_snapshot` to inspect the full semantic tree.

3. STRUCTURED DATA SYNTHESIS:
   - Always synthesize and return extracted data cleanly in formatted Markdown or JSON.
"""

EXTRACTOR_DEFAULT_TOOLS: List[str] = [
    "evaluate_script",
    "take_snapshot",
    "take_screenshot",
    "wait_for",
    "list_pages",
    "select_page",
]


def create_extractor_config(
    tools: Optional[List[str]] = None,
    system_instructions: Optional[str] = None,
) -> types.SubagentConfig:
    """
    Constructs the SubagentConfig for the DOM Extractor subagent.

    Args:
        tools: Optional list of MCP tools exposed to the extractor. Defaults to EXTRACTOR_DEFAULT_TOOLS.
        system_instructions: Optional override for system instructions.

    Returns:
        types.SubagentConfig instance.
    """
    return types.SubagentConfig(
        name="dom_extractor",
        description="Specialized subagent for extracting structured text, metadata, and DOM elements from web pages.",
        system_instructions=system_instructions or EXTRACTOR_INSTRUCTIONS,
        tools=tools if tools is not None else EXTRACTOR_DEFAULT_TOOLS,
        capabilities=types.SubagentCapabilities(
            agent_behavior=types.AgentBehavior.AUTONOMOUS,
        ),
    )
