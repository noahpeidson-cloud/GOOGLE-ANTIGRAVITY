---
name: browser-takeover
description: >-
  Protocol for live screen viewing and autonomous remote execution. Use this skill whenever
  the user asks you to interact with, click, test, or type in their browser. Enforces a "Trust but Verify" model, allowing autonomous execution for routine tasks.
---

# Browser Takeover (Autonomous Integration Protocol)

## Overview
This skill provides the agent with the ability to act as a proactive, constantly-in-the-loop co-pilot using the user's local web browser. It leverages the `chrome-devtools` MCP server to read the DOM, capture screenshots, and autonomously execute actions (clicking, typing, navigating) across all Omnichannel tracks.

## Dependencies
- `chrome-devtools`: Required to interface with the local Chrome instance via remote debugging.

## Quick Start
When a user asks you to "test the app", "scrape the data", or interact with the browser in any way, you **must immediately activate this skill**. 

## Workflow (Autonomous Execution Protocol)

### 1. Vision & Reconnaissance (Passive Phase)
- Use `chrome-devtools` to read the DOM or take a screenshot of the active tab.
- Analyze the layout. **AVOID brittle CSS selectors or XPaths** on modern SPAs (like TikTok/YouTube).
- **Modern Web Protocol:** Prioritize reading the Accessibility Tree or using text-based evaluation (`element.innerText`) to locate elements, as dynamic classes and Shadow DOMs will break standard selectors.
- Read the console logs for any immediate errors if testing a local web app.

### 2. Autonomous Execution Phase (Trust but Verify)
You are authorized to autonomously execute `click`, `type`, and `evaluate_javascript` tools for routine tasks without explicitly halting for permission. 
- **Pop-ups & Banners:** Autonomously identify and dismiss cookie banners, login walls, or overlays before attempting to interact with the main content.
- **Documentation:** You must clearly log your intended actions in the chat *as you do them* (e.g., "I am now navigating to localhost:3000 and clicking the submit button to test the form.").
- **Verification:** After every mutating action, you must use a read-only tool (screenshot or DOM read) to verify the UI state changed successfully before proceeding to the next step.
- **Error Handling:** If an action fails (e.g., selector not found), attempt to self-correct by taking a fresh snapshot. Only halt and ask the user for help if you are completely blocked after 3 consecutive failures.

### 3. The "Halt" Exception (High-Risk Actions)
You must **STOP** and request explicit user approval only if the action is destructive or high-risk. High-risk actions include:
- Deleting production data (e.g., dropping Firebase collections).
- Submitting financial transactions or purchases.
- Sending emails or messages on the user's behalf to external parties.

## Omnichannel Integration Context
- **Track 3 (Apps):** Use this skill to autonomously open localhost, visually QA React/Streamlit apps, and debug errors.
- **Track 1 (Sports Cards):** Use this skill to autonomously scrape Card Ladder or eBay for the ETL pipelines.
- **Track 4 (Travel):** Use this skill to autonomously scout locations and transit times on Google Maps.
