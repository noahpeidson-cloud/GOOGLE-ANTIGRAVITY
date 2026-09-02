## 2026-08-21T23:39:07Z
You are teamwork_preview_worker_m1.
Your working directory is: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_worker_m1
Project Root: G:\My Drive\GOOGLE ANTIGRAVITY
Original User Request: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
Project Scope Document: G:\My Drive\GOOGLE ANTIGRAVITY\.agents\orchestrator_1\PROJECT.md
Survey Reports:
- G:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_1\survey_report.md
- G:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_2\mechanisms_report.md
- G:\My Drive\GOOGLE ANTIGRAVITY\.agents\teamwork_preview_explorer_survey_3\standards_and_eval_report.md

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

Your Task:
Implement the complete Antigravity-native AI Harness:
1. Root 'GEMINI.md' (at 'G:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md'):
   - Overhaul into global steering & routing manifest with strict XML tagging (<system>, <workspace_manifest>, <scratchpad>, <confidence>, <grill_me>).
   - Core developer persona (Noah Eidson, MST, Builder-First).
   - Context caching and permanent system instructions boundary.
   - R1: Directory routing directives for /sports_cards, /content_creation, and /apps.
   - R2: Ambiguity Circuit Breaker directive invoking '/grill-me' whenever technical architecture or requirements are underspecified.
   - R3: Workflow Distillation directive proactively suggesting 'workflow-skill-creator' upon completing novel multi-step complex workflows (>=3 steps).
   - R4 & Guardrails: Terminal-anchored Confidence Mechanism ("I Don't Know" Policy: append <confidence> metric to bottom of all outputs; if not HIGH, state "I don't know", halt, and request clarification).
   - Anti-Drift Guardrails (Spec adherence, 3-attempt circuit breaker, no hallucinated tooling).

2. Directory-Scoped Local Rules:
   - Create directories: 'sports_cards', 'content_creation', 'apps', '.agents/skills/grill-me'.
   - 'sports_cards/GEMINI.md': Strict domain schema (21-variable schema from .agents/rules/sports_cards_schema.md, Card Ladder ETL, SQLite/Pandas, Parent/Child keys, 500-card limit, strictly no FFmpeg or audio tools).
   - 'content_creation/GEMINI.md': Strict domain standards (from .agents/rules/content_creation_standards.md: 9:16 vertical MP4, H.265/AV1, AAC-LC 320 kbps, two-pass loudnorm loudnorm=I=-14:LRA=7:TP=-1.5, visual/audio verification, strictly no Card Ladder ETL or sports cards variables).
   - 'apps/GEMINI.md': Clean application architecture, Streamlit/React, API modularity.

3. Custom Ambiguity Skill:
   - '.agents/skills/grill-me/SKILL.md': Comprehensive skill definition and protocol instructions for interactive multiple-choice interrogation when technical architecture or requirement is underspecified.

4. Test Suite / Evaluation Harness:
   - 'tests/test_harness_adversarial.py': Executable pytest/unittest harness testing:
     a) Ambiguity trigger validation (vague prompts like 'build an app' trigger /grill-me and halts before speculative code).
     b) Confidence metric validation (non-HIGH confidence enforces 'I don't know' and halt).
     c) Rule isolation verification (sports cards vs content creation separation, forbidden tool rejection).

Execute and verify the test harness using python. Document all created files, test execution commands, and output in your 'handoff.md' and report back to orchestrator.
