---
name: omnichannel-splitter
description: Orchestrates the gdrive MCP to read raw voice memos or notes and format them into YouTube, TikTok, and Snapchat scripts.
---

# Omnichannel Content Splitter

## Overview
This skill acts as an automated pipeline for converting raw brain dumps, voice memos, or unformatted text into perfectly structured scripts for YouTube, TikTok, and Snapchat. It relies on the `gdrive` MCP for document read/write operations.

## Invocation Triggers
Trigger this skill when the user provides a raw text dump, a Google Doc link containing notes, or explicitly asks to "split this idea" or "create scripts from this memo."

## Step-by-Step Execution
1. **Data Ingestion (Read):**
   - If the user provides a Google Doc link or file ID, use `gdrive` MCP's `readGoogleDoc` or `readTextFile` to extract the raw text.
   - If the user provides local text, parse it directly.
2. **LLM Transformation (Split):**
   Process the raw text into three distinct artifacts:
   - **YouTube Outline**: A structured 10-minute long-form video outline with specific B-roll visual cues and chapter markers.
   - **TikTok Script**: A fast-paced 60-second script focusing entirely on a strong 3-second visual hook and rapid delivery.
   - **Snapchat Story**: A rapid, 4-part story concept designed to feel intimate and behind-the-scenes.
3. **Data Persistence (Write):**
   - Autonomously use the `gdrive` MCP `createGoogleDoc` tool to save these three artifacts as perfectly formatted new documents in the user's Drive.
   - Return the URLs of the created Google Docs to the user.

## Constraints
- Do NOT hallucinate content completely outside the scope of the user's raw notes. Enhance and structure, but retain the core message.
- Always append the `<confidence>` block at the end of execution to verify successful `gdrive` document creation.
