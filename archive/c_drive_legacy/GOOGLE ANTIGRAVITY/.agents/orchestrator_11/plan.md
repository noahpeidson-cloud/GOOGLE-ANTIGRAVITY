# Orchestration Plan — S26 AI Camera Controller

## Objective
Develop a production-grade proof-of-concept AI-assisted real-time camera settings controller for Samsung Galaxy S26 Ultra in EDM concert environments (e.g. Sunbar), meeting requirements R1 (offline on-device ML/heuristics), R2 (Samsung Camera Pro Video UI automation via accessibility/taps/intents), and R3 (reactive trigger system for extreme lighting deviations like pitch-black dropouts or intense lasers), with <500ms verifiable trigger latency in Airplane Mode.

## Working Directory
`C:\Users\noahp\teamwork_projects\s26_ai_camera_controller`

## Architecture Phases

### Phase 0: Survey
- Spawn 3 Explorers in parallel:
  - Explorer 1: Target codebase audit (`C:\Users\noahp\teamwork_projects\s26_ai_camera_controller`), project structure, environment, Python/Android dependencies.
  - Explorer 2: Offline ML & Heuristic Light Analysis Architecture (TFLite/NumPy/OpenCV local algorithms, histogram/luminance anomaly detection, pitch-black dropouts vs laser spikes).
  - Explorer 3: Samsung Camera Pro Video UI Automation & Intent/Accessibility Tap Architecture (ADB input tap, accessibility intent, AutoInput/Tasker coordinates mapping for ISO/Shutter sliders, latency optimization <500ms).

### Phase 1: PROJECT.md & Feature Inventory Decomposition
- Merge findings into `PROJECT.md` with strict Feature Inventory and Milestones:
  - M1: Offline ML & Light Level Analyzer (offline frame/luminance ingestion, TFLite/heuristic model, feature extraction).
  - M2: Samsung Camera Pro Video UI Controller & Slider Automation (touch coordinate mappings for ISO & Shutter, ADB/accessibility dispatch engine).
  - M3: Reactive Event Trigger Engine & Threshold State Machine (debounce, laser spike detection, blackout detection, hysteresis, reactive trigger logic).
  - M4: Integration CLI / Real-Time Controller Daemon (end-to-end pipeline, offline execution verification, <500ms dispatch pipeline).
  - M5: E2E Testing Suite (Tiers 1-4) + Adversarial Hardening (Tier 5) + Forensic Audit.

### Phase 2: Execution & Verification Loop
- Run Explorer -> Worker -> Reviewer -> Challenger -> Auditor cycles for each milestone.
- Verify pass criteria and binary audit veto.

### Phase 3: Final Delivery & Handoff
- Deliver comprehensive handoff report to parent caller agent.
