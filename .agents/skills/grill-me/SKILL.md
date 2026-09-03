---
name: grill-me
description: A relentless adversarial interview protocol to sharpen a plan, architecture, or design. Enforces necessity testing, R1 Red Phase assertions, D: drive isolation, and recency bias checks.
disable-model-invocation: true
---

# Grill-Me Adversarial Review Protocol

## Overview
`grill-me` is a high-scrutiny, adversarial evaluation protocol designed to expose speculative designs, untested assumptions, and context rot before code execution begins.

## Core Examination Pillars

### 1. Necessity & ROI Testing
- Why does this feature or daemon need to exist?
- What fails if we do NOT build it?
- Can this be accomplished with an existing tool, CLI command, or lightweight script?

### 2. Zero-Discretion & R1 Testability
- How will success be deterministically proven?
- What is the failing Red Phase test assertion?
- Are we relying on subjective model assertions or reproducible test runner exit codes?

### 3. Storage & Workspace Boundaries
- Does this component write state or cache to `C:` drive?
- Is state isolated to `D:\GOOGLE ANTIGRAVITY` or `D:\AI_Platform`?
- Are raw assets immutable with non-destructive backups in `.archive/`?

### 4. Recency Bias & Context Health
- Are we reacting to the last 2 conversation turns or anchoring to filesystem truth?
- Does this introduce prompt bloat or violate the static-to-dynamic prefix order?
- Should large outputs be offloaded to disk instead of raw context?

## Usage
1. **Trigger Protocol**: Invoke when planning architectural changes, new daemons, or multi-agent delegation.
2. **Review Assertions**: Interrogate every proposed change against the 4 pillars.
3. **Approve or Reject**: Reject speculative concepts; approve only benchmarked, deterministic designs.

## Examples
- **Example 1**: Grilling an autonomous 8K ingest daemon: *"Why run a standing background loop on D:\Downloads instead of an event-triggered CLI invocation? What is the CPU/RAM overhead and debounce failure mode?"*
- **Example 2**: Grilling a vector memory hub: *"Why embed 475 uncurated chat logs into prompt context instead of querying an indexed, curated SQLite knowledge store?"*