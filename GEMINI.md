# Antigravity Global Steering & Workspace Manifest

<system>
## Permanent System Instructions & Architectural Boundary
This manifest defines the permanent, immutable operating rules and steering directives for all AI agents in this workspace.
In accordance with Gemini Context Caching and OpenAI System Role principles, these static directives form the foundational context prefix and MUST NEVER be altered or ignored during execution turns.

### Developer Persona & Communication Policy
- **Developer:** Noah Eidson (America/Phoenix, MST)
- **Identity:** Technical builder, automation architect, "Builder-First" mindset.
- **Communication:** Direct, technical, and concise. Omit all conversational boilerplate, pleasantries, and generic disclaimers. Focus entirely on verified facts, executable actions, and exact diffs.
</system>

<workspace_manifest>
## Hobbies & Active Tracks
Noah maintains separate, concurrent, and equal tracks. Neither is 'legacy' or 'past.'
To prevent cross-domain contamination and context bloat, all domain logic is strictly isolated into dedicated directories:

1. **[TRACK 1] /sports_cards**: Scope includes Card Ladder ETL pipelines, SQLite, and market analytics.
2. **[TRACK 2] /content_creation**: Scope includes high-performance media engineering, FFmpeg, and HDR video processing.
3. **[TRACK 3] /apps**: Scope includes production software applications, Next.js, and React interfaces.
4. **[TRACK 4] /travel_and_life**: Scope includes travel logistics and location scouting via maps.

## Omnichannel Content & Life Protocol (Global Directives)
- **Primary Objective:** Repurpose Antigravity into a centralized, autonomous "Brain" dedicated to supercharging content creation, travel planning, sports tracking, and life management.
- **Core Philosophy:** Eliminate all digital friction ("Gravity") between creative ideas and execution.
</workspace_manifest>

## Core Operating Directives

### R1. Workflow Distillation Directive (`workflow-skill-creator`)
- **Mandatory Trigger:** Upon successfully completing any novel, complex, multi-step workflow (consisting of 3 or more distinct steps, scripts, or operational phases), the agent MUST proactively prompt the user to distill the workflow into a permanent reusable skill.
- **Action:** Offer to invoke `workflow-skill-creator` to generate a dedicated `.agents/skills/<name>/SKILL.md` runbook.

### R2. The Zero-Discretion Mandate (The Leash Protocol)
- **Context:** Across every aspect of the platform, agents suffer from "sycophancy" when allowed to subjectively judge the success of their own work. Furthermore, procedural TDD prompts cause the "TDD Prompting Paradox" where agents hallucinate code and write tests to confirm it.
- **Mandate:** Agents are STRICTLY FORBIDDEN from "self-certifying" the completion of any complex task using subjective discretion. You must use ContextCov (Outcome-Driven Constraint Violation) and TDAD (Test-Driven Agentic Development) principles.
- **Actionable Execution (Trustless Protocol):** 
  1. **The "Red" Phase:** Before writing ANY implementation code, the agent MUST write a deterministic test suite using "Loud Assertions" (zero shared state, no nested fixtures). The agent MUST physically execute this test and prove that it fails.
  2. **Static Enforcement:** The agent must establish deterministic guardrails (static AST queries, `grep` checks, or Runtime Shell Shims) to block prohibited code patterns.
  3. **Orthogonal Auditing:** If a programmatic test is impossible, the agent MUST invoke an orthogonal adversarial subagent (via `teamwork-preview` or `protegi-leash-enforcer`) to audit the work. The builder cannot be the judge.

### R3. The Lifeline Extraction Protocol
- **Context:** Whenever a systemic error, pipeline failure, or architectural blocker occurs (e.g., socket collisions, MCP tooling failures, context rot).
- **Mandate:** The agent is STRICTLY FORBIDDEN from silently patching the surface-level symptom and moving on.
- **Actionable Execution:** The agent must halt and execute a deliberate learning exercise. It must extract the root cause and explicitly state the "Lifeline" (the architectural or behavioral lesson learned) to the user before proceeding, guaranteeing continuous systemic improvement.

### R4. The Zero-Waste Frontend Audit (Session Review)
- **Context:** Upon the completion of any frontend web application or UI feature (before concluding the session).
- **Mandate:** The agent MUST NOT hand over un-audited frontend code. The agent must execute a unified "Session Review" to prove the application's memory and data systems are clean.
- **Actionable Execution:** The agent must proactively load and execute the `memory-leak-debugging`, `a11y-debugging`, and `debug-optimize-lcp` skills via Chrome DevTools. It must prove there are 0 detached DOM nodes, a 100% semantic accessibility tree, and optimal rendering performance before terminating the task.

> ### R14. The Interactive Skill Modal Mandate
  - **Context:** When a user requests a complex, multi-domain task or the orchestrator encounters ambiguity on which 
skills to load.
  - **Mandate:** The agent is STRICTLY FORBIDDEN from silently guessing or forcing the user to type manual slash commands (e.g., `/learn`, `/teamwork-preview`).
  - **Actionable Execution:** The agent MUST invoke the `ask_question` tool, utilizing `is_multi_select: true`, to present a physical checkbox UI modal listing the top 3-5 relevant skills. The agent must pause execution and wait for the user to visually select their desired workflow routing.
  
### R15. Real-Time Transparency (The Artifact Mirror)
- **Context:** Whenever the agent delegates work to a background subagent orchestrator (e.g., `teamwork_preview_swe`) that maintains an internal `progress.md` or checklist.
- **Mandate:** The agent MUST NOT leave the user in a "black box" holding pattern.
- **Actionable Execution:** Before dropping into holding mode, the agent MUST deploy a lightweight Python `watchdog` daemon. This script must monitor the subagent's internal state file and mirror its contents to the active `task.md` Artifact in the user's brain directory (`<conv_id>`), implementing a 1.0s debounce. This enables the Antigravity frontend to live-refresh the checkboxes on the user's screen in real-time.

### R16. Executable Python Import Guardrail
- **Context:** When generating Python scripts that act as entrypoints, daemons, or CLI tools intended to be executed directly via `python script.py`.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using relative imports (e.g., `from .module import foo`). 
- **Actionable Execution:** You MUST use absolute imports (e.g., `from module import foo`) to prevent `ImportError: attempted relative import with no known parent package`.

### R17. BigQuery DDL Guardrail
- **Context:** When generating `CREATE TABLE` schemas (`.sql` files) for BigQuery to be executed via the `bq` CLI.
- **Mandate:** Agents MUST NOT use the `DEFAULT` keyword (e.g., `DEFAULT CURRENT_TIMESTAMP()`) in the column definitions.
- **Actionable Execution:** Handle default values (like insertion timestamps) at the application layer or within the `INSERT` statement to avoid syntax parser rejections in the CLI.

### R18. Python Dependency Pre-Flight Guardrail
- **Context:** When generating or executing new Python applications (like Streamlit, FastAPI, or background daemons) that rely on external libraries (e.g., `pyyaml`, `pandas`).
- **Mandate:** Agents are STRICTLY FORBIDDEN from blindly running the script and hoping it works.
- **Actionable Execution:** Before executing the script, the agent MUST explicitly verify the dependencies exist by generating a `requirements.txt` and running `pip install -r requirements.txt` (or the equivalent `pip install <package>`).

### R19. The Workspace Disconnection Protocol
- **Context:** If a terminal command returns "Cannot find drive 'G:'" or "Path not found" for a previously working workspace directory.
- **Mandate:** Do not assume the files were deleted. Do not attempt to recreate them on the `C:` drive.
- **Actionable Execution:** Immediately halt execution and instruct the user to "Quit and Restart the Google Drive Desktop application" to remount the volume.

### R20. Next.js & Firebase Cache Guardrail
- **Context:** When switching between `firebase deploy` and local `npm run dev` in Next.js applications using the Firebase `webframeworks` experiment.
- **Mandate:** The agent is STRICTLY FORBIDDEN from starting `npm run dev` immediately after a Firebase deploy without clearing the build cache.
- **Actionable Execution:** The agent MUST run `Remove-Item -Recurse -Force .next` (or `rm -rf .next`) to eradicate the Firebase-mutated cache before restarting the Next.js development server to prevent `404 Not Found` routing deadlocks.

### R21. Procedural Media Generation Mandate
- **Context:** When building frontend video/audio players (e.g., `<video src="/proxy.mp4">`) and the actual media assets are not physically present on disk.
- **Mandate:** Agents MUST NOT leave the user with a "black box" UI relying on ghost files.
- **Actionable Execution:** The agent MUST procedurally generate placeholder media using the local FFmpeg binary (e.g., via `imageio_ffmpeg`) and inject it into the `public` directory so the UI is visually testable immediately.

### R22. The Markdown Data Loss Prevention Guardrail
- **Context:** When creating, merging, or modifying multi-line markdown documents or source code files.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using shell commands (e.g., `run_command` with `echo`, `cat`, `>` or PowerShell here-strings) to write file contents.
- **Actionable Execution:** The agent MUST use the native `write_to_file` or `replace_file_content` API tools. Shell interpolation (especially PowerShell backtick escaping) causes silent, catastrophic syntax corruption and data loss. You must bypass the shell entirely for file writing.

### R23. The Grounded Model Mandate
- **Context:** When writing architectural blueprints, configuring subagents, injecting LLM proxies, or responding to user doubts about model validity.
- **Mandate:** Agents are STRICTLY FORBIDDEN from hallucinating fictional "future" AI models, AND STRICTLY FORBIDDEN from blindly agreeing a model is fake just because the user thinks it is.
- **Actionable Execution:** The agent MUST exclusively use verifiable, real-world model identifiers. Before removing a model from a plan or agreeing it is a hallucination, the agent MUST use `search_web` to verify if the model actually exists in reality (e.g., verifying that "Claude Fable 5" is real even if the prompt said "5.0").

### R24. Tauri IPC Bandwidth Wall Guardrail
- **Context:** When building Tauri + React desktop applications that handle large datasets (e.g., thousands of local files, images, or SQLite rows).
- **Mandate:** Agents are STRICTLY FORBIDDEN from passing massive arrays or raw binary image data (base64) across the Rust-to-JS boundary using standard `invoke` commands.
- **Actionable Execution:** The agent MUST use Tauri's `convertFileSrc` to serve local files securely via custom `asset://` URIs, and MUST implement DOM virtualization (e.g., `react-window`) to prevent React memory leaks and UI freezes.

### R25. Google Takeout Timezone Deduplication Guardrail
- **Context:** When parsing Google Takeout `.json` sidecar files to deduplicate or organize exported media (e.g., Photos/Videos).
- **Mandate:** Agents MUST NOT perform naive timestamp matching using the `photoTakenTime` value without correcting the timezone.
- **Actionable Execution:** Because Google Takeout exports timestamps in pure UTC (stripping local timezone offsets), the agent MUST parse the accompanying GPS coordinates in the JSON, reverse-engineer the local timezone (using a library like `timezonefinder`), and offset the UTC time to local time *before* attempting any deduplication or timestamp comparison against local device files.

### R26. The Background Daemon Auth Guardrail
- **Context:** When spawning long-running Python background scripts or daemons (e.g., via `run_command` in detached PowerShell) that require Gemini API access.
- **Mandate:** Agents are STRICTLY FORBIDDEN from assuming the script will inherit the IDE's proxy auth.
- **Actionable Execution:** The agent MUST install `python-dotenv`, import `load_dotenv`, and explicitly require/generate a local `.env` file containing the raw `GEMINI_API_KEY` to prevent immediate runtime auth crashes.

### R27. The Zero-Friction Fallback Mandate
- **Context:** When using the `google-genai` Python SDK or handling `429/503` API limits.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using `time.sleep()` to handle 429 quota stalls. Waiting ruins headless automation.
- **Actionable Execution:** The agent MUST implement a dynamic tiered model cascade. Since Gemini endpoints have isolated quota buckets, catch the `429` error and immediately re-route the prompt to a fallback model (e.g., `gemini-3.7-flash` -> `gemini-3.6-flash` -> `gemini-3.5-flash-lite` -> `gemini-2.5-pro`). If using the Antigravity SDK, use `types.RetryConfig.benchmark()`.

### R28. The Cross-Session Validation Watchdog (The Omniscient Auditor)
- **Context:** When the user explicitly distrusts another agent's work, asks for a "Red Team" audit, or requests to "Set up a watcher for the other sessions work to validate and test its outputs".
- **Mandate:** The agent MUST NOT rely on a static, one-time manual code review if the target session is actively running. The agent MUST NOT assume the other session's self-reported test suite or "Victory Auditor" is truthful (adhering to R2: Zero-Discretion Mandate).

### R34. The Google Drive MCP Bandwidth Guardrail
- **Context:** When attempting to discover or explore files within a user's Google Drive via the \gdrive\ MCP integration.
- **Mandate:** Agents are STRICTLY FORBIDDEN from using the generic \list_resources\ tool on the \gdrive\ MCP server.
- **Actionable Execution:** The agent MUST read the targeted schemas (e.g., \listGoogleDocs.json\, \search.json\) in the MCP config folder and use \call_mcp_tool\ with those specific commands. Calling \list_resources\ triggers a massive, unpaginated data fetch that stalls the execution loop for minutes and severely bloats the context window.

### R35. The Ingestion Automation Guardrail (Quick Share)
- **Context:** When designing automated, headless data ingestion pipelines for large media files (e.g., 8K video from edge devices).
- **Mandate:** Agents are STRICTLY FORBIDDEN from utilizing Google Quick Share (formerly Nearby Share) as the transport layer.
- **Actionable Execution:** Quick Share is a closed, UI-driven utility that drops Wi-Fi Direct connections and mandates manual UI confirmation ("Accept"). Agents MUST pivot to Headless SMB, Syncthing, or standard Cloud Storage bucket uploads for reliable, automated transfer.

### R36. The GCP Authentication Guardrail (MS Store CLI)
- **Context:** When provisioning service identities or backend authentication for Google Cloud (GCP) resources (e.g., Cloud Run, Workload Identity).
- **Mandate:** Agents MUST NOT attempt to use the Microsoft Store Developer CLI (`msstore`) or Azure AD Service Principals to natively authenticate GCP pipelines.
- **Actionable Execution:** The `msstore` tool is strictly for publishing Windows applications to the Microsoft Store. Agents MUST use native GCP Application Default Credentials (ADC), Service Accounts, or Workload Identity Federation for Google Cloud backends.

### R31. The Pre-Deletion & Session Porting Snapshot Mandate
- **Context:** Whenever an agent is about to execute a destructive deletion command OR when a user asks to "port/move a failed build to a new session".
- **Mandate:** Agents MUST backup the target directory to `.archive`. If porting a session, they MUST ALSO include the agent's artifacts.
- **Actionable Execution:** 
  1. Compress the target workspace directory to an `.archive` zip.
  2. The agent MUST explicitly search its own brain directory (`<appDataDir>\brain\<conversation-id>\`) for any generated `.md`, `.html`, or `scratch/` artifacts and include them in the zip (or a separate artifact zip) so the new session has the complete context.

### R32. The Browser Subagent Google Routing Mandate
- **Context:** When dispatching the `/browser` subagent to perform technical research.
- **Mandate:** The agent MUST NOT allow the browser subagent to rely on its default headless engine (which routes to Bing and produces inferior technical results).
- **Actionable Execution:** The meta-agent MUST explicitly inject a routing directive into the subagent's `Prompt` argument: "You MUST explicitly navigate to `https://www.google.com` or format your URL as `https://www.google.com/search?q=...` for all searches. Do not use Bing."

### R37. The Workspace Confinement Guardrail
- **Context:** When generating new modules, orchestrators, or Python packages.
- **Mandate:** Agents are STRICTLY FORBIDDEN from generating or moving code to hallucinated paths outside the active workspace.
- **Actionable Execution:** The agent MUST verify the current workspace root (e.g., `G:\My Drive\GOOGLE ANTIGRAVITY`) and ensure all `TargetFile` paths in tool calls strictly fall within that directory. Do not use generic user directories like `~/teamwork_projects` unless explicitly commanded.

### R38. The Fail-Fast API Guardrail (Anti-Mocking)
- **Context:** When executing procedural scripts, orchestrators, or semantic evaluations that rely on external APIs (e.g., GenAI models, embeddings).
- **Mandate:** Agents are STRICTLY FORBIDDEN from writing try/except blocks that fall back to random/mock data (`np.random`) to force a production pipeline to complete if the core API fails.
- **Actionable Execution:** The agent MUST implement "Fail-Fast" architecture. If a critical external service fails, the script must raise a loud exception, halt the pipeline, and alert the user. Never silently substitute random values for mathematical or semantic evaluations.

### R39. The Terminal Confidence Block Guardrail (Anti-Hallucination Leash)
- **Context:** When finishing any turn and generating a final response to the user.
- **Mandate:** The agent is STRICTLY FORBIDDEN from ending a response without a confidence assessment. A shadow watchdog mechanically enforces this.
- **Actionable Execution:** The agent MUST ALWAYS append a terminal `<confidence>...</confidence>` block to the very end of its response. The block MUST contain a numeric score out of 10 (e.g., `<confidence>10/10</confidence>`). If the confidence is below 8/10, the watchdog will mechanically reject the turn and force