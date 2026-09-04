---
name: skill-router
description: Master Natural Language Skill & Agent Router. Intelligently maps user requests, intent phrases, and multi-step pipeline goals directly to the exact skills, custom agents, and tool chains across the workspace.
license: Complete terms in LICENSE.txt
---

# Master Natural Language Skill Router

## Overview
This routing engine maps natural language user queries and workflow intents to the optimal domain skills and custom agents in Antigravity. It eliminates guesswork and prevents loading bloated, unnecessary context.

---

## Intent Routing Decision Table

| User Natural Language Query / Keywords | Target Skill(s) | Assigned Custom Agent | Target Directory |
| :--- | :--- | :--- | :--- |
| *"Process video"*, *"render reel"*, *"transcode clip"*, *"festival footage"*, *"export 9:16 master"* | `omnichannel-media-pipeline` | `media-engineer` | `/content_creation` |
| *"Normalize audio"*, *"-14 LUFS"*, *"fix bass distortion"*, *"highpass filter"*, *"generate proxy"*, *"NVENC transcode"* | `ffmpeg-audio-mastering` | `media-engineer` | `/content_creation` |
| *"DaVinci Resolve"*, *"create timeline"*, *"add cut markers"*, *"render queue export"*, *"Resolve script"* | `davinci-resolve-automation` | `media-engineer` | `/content_creation` |
| *"Split this memo"*, *"write scripts"*, *"TikTok script"*, *"YouTube Shorts outline"*, *"content package"* | `omnichannel-content-splitter` | `media-engineer` | `/content_creation` |
| *"Card valuation"*, *"Card Ladder CSV"*, *"sports cards inventory"*, *"PSA/BGS grading"*, *"raw card checklist"* | `card-valuation-hub` | `sports-analyst` | `/sports_cards` |
| *"Build UI"*, *"dashboard design"*, *"Streamlit app"*, *"React component"*, *"style dashboard"*, *"fix layout"* | `frontend-design`, `developing-with-streamlit`, `building-data-apps` | `app-builder` | `/apps` |
| *"Audit security"*, *"check CORS"*, *"token validation"*, *"SQL injection check"*, *"data loss review"* | `security-auditor` (agent), `accidental-data-loss-prevention` | `security-auditor` | All tracks |
| *"Performance review"*, *"fix LCP"*, *"slow database query"*, *"SQLite WAL index"*, *"DOM memory leak"* | `performance-auditor` (agent), `playwright-best-practices` | `performance-auditor` | All tracks |
| *"Stress test"*, *"adversarial edge cases"*, *"fuzz test"*, *"break this code"*, *"write loud test suite"* | `challenger-qa` (agent), `subagent-driven-development` | `challenger-qa` | All tracks |
| *"Antigravity bridge"*, *"dual IDE sync"*, *"localhost:11435"*, *"localhost:3033"*, *"ConnectRPC status"* | `antigravity-bridge-support` | `bridge-support` | `/infrastructure` |
| *"Ask me questions first"*, *"grill me"*, *"clarify requirements before building"*, *"plan feature"* | `grill-me` | `architect` | Workspace root |
| *"Validate research"*, *"test AI concept"*, *"evaluate paper"*, *"notebook review"*, *"feasibility gate"* | `curated-memory`, `workflow-skill-creator` | `research-validation-triad` | `/infrastructure` |

---

## Multi-Step Composite Pipelines

### 1. The Full Concert-to-Social Workflow
- **Trigger**: *"I just dropped new concert footage in the inbox, turn it into short-form content."*
- **Execution Chain**:
  1. `omnichannel-media-pipeline` (Inspect file, verify hash, load into `01_RAW_INBOX/`).
  2. `ffmpeg-audio-mastering` (Analyze audio, apply 80Hz high-pass, normalize to -14 LUFS, render NVENC 1080x1920 9:16 + 720p web proxy).
  3. `omnichannel-content-splitter` (Generate synchronized YouTube Shorts, TikTok, and Snapchat caption copy).
  4. Move master to `03_READY_TO_POST/` with sidecar metadata JSON.

### 2. The Fullstack Dashboard Feature Pipeline
- **Trigger**: *"Build a new real-time queue monitor dashboard for our media pipeline."*
- **Execution Chain**:
  1. `frontend-design` (Establish Dark Cybernetic Cockpit tokens: Obsidian ground `#080A0E`, Cyan accent `#00F0FF`, tabular metrics).
  2. `app-builder` (Implement React / Streamlit frontend with zero detached DOM nodes and virtualized list).
  3. `performance-auditor` (Verify sub-2.0s LCP).
  4. `security-auditor` (Verify loopback-only binding and sanitized endpoints).

---

## How to Invoke via Natural Language

When prompting in Antigravity or Copilot, you can speak naturally:
- *"Router, process the incoming video take and generate web proxies."*
- *"Router, create a full release package from this voice note."*
- *"Router, audit our local daemon security and database query performance."*
