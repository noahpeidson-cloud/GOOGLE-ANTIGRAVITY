# Handoff Report: Android CLI Automation & Next.js Command Center Specification

**Agent:** `spec_miner_android_frontend`  
**Parent:** `0ed1cf9f-fb22-4a88-aa7e-30539e35df1b` (`parent`)  
**Timestamp:** 2026-08-25T18:49:15Z  
**Type:** Hard Handoff (Task Complete)

---

## 1. Observation

1. **Android CLI and ADB Capabilities**:
   - `C:\Users\noahp\.gemini\config\plugins\android-cli-plugin\skills\SKILL.md` (lines 70-201): Defines CLI interface for `android layout [-d] [-p] [-o=PARAM] [--device=PARAM]`, `android screen capture [-o=PARAM] [--annotate]`, `android screen resolve`, and `android emulator`.
   - `C:\Users\noahp\.gemini\config\plugins\android-cli-plugin\skills\references\interact.md` (lines 8-17): Defines the JSON schema for UI layout dumps containing `bounds` `[minX,minY][maxX,maxY]`, `center` `[x,y]`, `text`, `resourceId`, `interactions` (`clickable`, `scrollable`, etc.), and `state` (`focused`, `checked`).
   - `g:\My Drive\GOOGLE ANTIGRAVITY\.agents\skills\zero-touch-mobile-provisioning\SKILL.md` (lines 10-73): Enforces Rule R10.2 (4-tier hierarchy: Dalvik/Binaries -> Intents -> UIAutomator -> Keystrokes), requiring `%s` space encoding in `input text` and disabling Samsung Auto Blocker via `settings put global rampart_auto_enabled_switch_enabled 0`.

2. **Modern Web Guidance for Command Center Dashboard**:
   - Running `npx.cmd -y modern-web-guidance@latest search "dashboard layout real-time performance"` returned `efficient-background-processing` and `interactions-in-complex-layouts`.
   - Retrieving `efficient-background-processing` established the requirement for `content-visibility: auto` paired with `contain-intrinsic-size` and listening to `contentvisibilityautostatechange` to pause high-frequency polling/SSE streams when dashboard cards are offscreen.

3. **Subsystem Daemons & Workspace Context**:
   - `sports_cards/ecosystem_hub/api.py` & `app.py`: FastAPI daemon on port 8000 handling portfolio metrics and Card Ladder scraping.
   - `media_pipeline/boot_pipeline.py` (lines 16-32): Daemons for Android Wi-Fi ingestion and PySpark Gemini-Omni grading.
   - `apps/agy_mobile/package.json` (lines 11-25): Next.js 16.3.2, React 19.2.8, Tailwind CSS v4 setup.

---

## 2. Logic Chain

1. **Mobile Scraper Integration**:
   - Direct web DOM scraping on mobile video platforms (TikTok, Instagram, YouTube Shorts) suffers from aggressive anti-bot scripts and obfuscated classnames.
   - Using `android layout` JSON dumps provides direct access to native accessibility labels, engagement text nodes (`like_count`, `title`), and precise pixel bounding boxes.
   - By parsing `bounds="[x1,y1][x2,y2]"` to calculate center coordinates `(x1+x2)/2, (y1+y2)/2`, Python can synthesize non-brittle touch taps via `adb shell input tap` and vertical gestures via `adb shell input swipe`.

2. **Next.js Real-Time Architecture**:
   - Dashboard users require live updates on multi-step ingestion, PySpark grading, and CardLadder scraping.
   - Unidirectional telemetry is best served by Server-Sent Events (SSE) from FastAPI (`/api/v1/events/stream`), while bidirectional commands (manual device control) use WebSockets.
   - To prevent frame drops and high Interaction to Next Paint (INP) latency during rapid telemetry streaming, dashboard cards must use CSS containment (`content-visibility: auto`) and throttle stream consumption when scrolled offscreen.

3. **Deterministic Testing Strategy**:
   - Because physical Android devices and emulators are not guaranteed to be present in CI/test environments, an in-memory `MockAndroidDeviceState` test harness is essential.
   - Testing must use Loud Assertions (Rule R2): verifying exact mathematical center calculations, space escaping `%s`, error recovery on device disconnect, and deterministic React component rendering via Vitest + React Testing Library + MSW.

---

## 3. Caveats

1. In headless/container CI environments where neither `android` CLI nor `adb` are installed on the host PATH, production code must use the fallback XML `uiautomator dump` or mock adapter.
2. The Next.js dashboard must implement auto-discovery or port-offset retry for FastAPI backends to prevent `WinError 10048` socket collisions if port 8000 is occupied.

---

## 4. Conclusion

The specification mining phase is complete. All commands, schemas, architecture diagrams, modern web performance guidelines, and deterministic test blueprints have been thoroughly documented in `.agents/spec_miner_android_frontend/report.md`. The orchestrator and implementation agents have an authoritative, zero-ambiguity foundation to build the Next.js Command Center, the Android CLI viral scraper, and the backend resiliency layer.

---

## 5. Verification Method

To independently verify the findings and specifications:
1. Inspect `.agents/spec_miner_android_frontend/report.md` for complete feature discovery and edge case tables.
2. Review the mock test harness code in Section 5.2 of `report.md` to verify deterministic Loud Assertion coverage.
3. Validate `modern-web-guidance` retrieval commands:
   ```bash
   npx.cmd -y modern-web-guidance@latest retrieve "efficient-background-processing,interactions-in-complex-layouts"
   ```
