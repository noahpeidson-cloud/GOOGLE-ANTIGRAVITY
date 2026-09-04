## 2026-08-25T05:26:44Z
You are explorer_m2_2.
Your working directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m2_2
The authoritative user request is at: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\ORIGINAL_REQUEST.md
The project specification is at: g:\My Drive\GOOGLE ANTIGRAVITY\PROJECT.md
The target project directory is: g:\My Drive\GOOGLE ANTIGRAVITY\.agents\cron

Task:
Investigate and design `detectors/ecosystem_pollution.py`, `detectors/secret_zero.py`, and `detectors/prompt_fatigue.py` for Milestone 2:
1. `detectors/ecosystem_pollution.py`:
   - Detects directories ending in `.disabled` in `.gemini/config/plugins` and across the workspace.
   - Detects cross-track domain boundary contamination (e.g. sports card files in `/content_creation`).
   - Emits `AnomalyRecord` with `DetectorType.ECOSYSTEM_POLLUTION`, `Severity.LOW` / `Severity.MEDIUM`.
2. `detectors/secret_zero.py`:
   - Scans `.env`, `.env.*`, `config.json`, `*.yaml`, `*.toml` for placeholder tokens (`your_token_here`, `YOUR_API_KEY_HERE`, `TODO_TOKEN`, etc.).
   - Emits `AnomalyRecord` with `DetectorType.SECRET_ZERO`, `Severity.CRITICAL`, masking sensitive values (`AIzaSyA***`).
3. `detectors/prompt_fatigue.py`:
   - Reads `GEMINI.md` manifest, counts total lines and estimates token count (word count * 1.3).
   - Flags when lines > 100 (`PROMPT_FATIGUE_MAX_LINES`), identifies duplicated rule headings.
   - Emits `AnomalyRecord` with `DetectorType.PROMPT_FATIGUE`, `Severity.MEDIUM`, recommending rule offloading to `vectorized-rule-registry`.
4. Write full specification and implementation blueprints to `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\explorer_m2_2\handoff.md`.
Update `progress.md` as you work. Send a message to parent when complete. Do not write implementation code directly.
