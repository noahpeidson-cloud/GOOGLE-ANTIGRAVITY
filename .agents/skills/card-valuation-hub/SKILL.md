---
name: card-valuation-hub
description: Launches the Checklist Valuation & Ingestion Hub. It spawns a local backend, verifies API keys, and renders a Generative UI for managing raw card checklists and exporting Card Ladder CSVs.
---

# Card Valuation Hub

Use this skill when the user asks to evaluate raw cards, parse trading card checklists, or generate Card Ladder CSVs.

## Workflow

1. **Scrape Checklist**: If the user provides a URL to a checklist (e.g., Beckett or Cardboard Connection), use the `chrome-devtools` MCP tools (`navigate_page`, `wait_for`, `take_snapshot`) to extract the checklist data into a structured JSON list of cards.
2. **Launch Backend**: Execute `python d:/GOOGLE ANTIGRAVITY/.agents/skills/card-valuation-hub/scripts/backend.py` as a background daemon to serve the WebSocket.
3. **Render UI**: Embed the UI in the chat using `<agent-embed src="file:///d:/GOOGLE ANTIGRAVITY/.agents/skills/card-valuation-hub/resources/valuation_hub.html"></agent-embed>`.

## Storage & Database Governance
- All portfolio databases (`card_inventory.db`) MUST live in `sports_cards/` on `D:\GOOGLE ANTIGRAVITY`.
- Maintains strict 21-variable schema integrity matching Card Ladder standards.

## Natural Language Invocations
- *"Evaluate this sports card checklist from Beckett"*
- *"Launch the card valuation hub and export Card Ladder CSV"*
- *"Parse raw card table and sync with local portfolio database"*
