## 2026-08-22T23:52:43Z
You are a Spec Miner subagent in the Viral Trend Pipeline Python integration test suite project.

Your Working Directory is: C:\Users\noahp\OneDrive\Desktop\Antigravity\.agents\spec_miner_pipeline_1
You MUST read:
- C:\Users\noahp\OneDrive\Desktop\Antigravity\.agents\ORIGINAL_REQUEST.md
- g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\viral-trend-pipeline\SKILL.md
- g:\My Drive\GOOGLE ANTIGRAVITY\GEMINI.md

Task:
1. Initialize your progress.md and BRIEFING.md in your working directory.
2. Mine and specify in deep detail:
   - The exact SQLite database schema for trends.db (columns: id, trend_name/tag, platform, category, date_added, engagement_metrics, etc.).
   - The exact SQLite Mark-and-Sweep garbage collection specification: query DELETE FROM trends WHERE date_added < date('now', '-14 days'), 30-day seeding strategy, verifying exact row counts before and after the sweep.
   - The exact BigQuery payload schema and transformation rules for AI.FORECAST and AI.KEY_DRIVERS: unnesting tag arrays, type casting/cleaning, case preservation, deduplication, structure requirements.
3. Outline the comprehensive test cases (Tier 1-4: Category-Partition, Boundary Value Analysis, Pairwise, Real-world workloads) for R2 and R3.
4. Write your full findings and specifications to handoff.md in your working directory.
5. Send a message to your parent with a concise summary and path to your handoff.md.
