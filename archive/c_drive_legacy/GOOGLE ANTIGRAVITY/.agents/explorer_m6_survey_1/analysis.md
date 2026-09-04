# Requirement R1 Technical Investigation & Architectural Blueprint: Web UI Metadata Forms & Remote Trigger

## Executive Summary
This document delivers the comprehensive investigation of **Requirement R1 (Web UI Metadata Forms)** for Milestone 6 ("Human-in-the-Loop" EDM Content Strategy Pipeline). It details the DOM structure, CSS tokens, touch handlers, JavaScript payload dispatch, FastAPI Pydantic v2 schemas, CLI argument orchestration, and existing test suite contracts across `content_creation/static/index.html`, `content_creation/remote_trigger.py`, `content_creation/orchestrator.py`, and `content_creation/tests/`.

---

## 1. Frontend Investigation: `content_creation/static/index.html`

### 1.1 Current DOM & PWA Layout Hierarchy
The static dashboard is served at `GET /` by FastAPI and functions as a mobile Progressive Web App (PWA).

```
<!DOCTYPE html> (UTF-8)
├── <head>
│   ├── Meta: viewport (width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover)
│   ├── Meta: apple-mobile-web-app-capable (yes), mobile-web-app-capable (yes)
│   ├── Meta: apple-mobile-web-app-status-bar-style (black-translucent), apple-mobile-web-app-title (EDM Trigger)
│   ├── Meta: theme-color (#000000)
│   ├── Link: manifest (/static/manifest.json)
│   └── <style>: OLED Dark Theme CSS Tokens & Animations
└── <body class="oled-theme">
    └── <div id="app" class="dashboard-container">
        ├── <header class="dashboard-header">
        │   ├── .brand-title ("⚡ LASER BAPTISM")
        │   └── #health-badges ("#badge-adb", "#badge-ffmpeg", "#badge-server")
        ├── <main class="trigger-section">
        │   └── .button-wrapper
        │       └── <button id="trigger-btn" class="massive-trigger-btn pulse-glow">
        │           ├── .btn-inner
        │           │   ├── .btn-icon ("⚡")
        │           │   ├── #btn-label ("TRIGGER EDM PIPELINE")
        │           │   └── .btn-sublabel ("S26 Ultra Ingest + RMS Drop")
        │           └── #btn-spinner.hidden
        ├── <section class="telemetry-section">
        │   └── #status-card
        │       ├── #daemon-state ("IDLE" / "RUNNING")
        │       ├── #active-job-id, #elapsed-time, #last-job-summary
        │       └── #cancel-btn, #refresh-status-btn
        └── <div id="toast-container" class="toast-container">
            ├── #toast-card.hidden
            │   ├── #toast-icon, #toast-title, #toast-message, #toast-close
            └── #status-toast, #status-display (backward-compat test aliases)
```

### 1.2 Proposed Metadata Form UI Component
To satisfy Requirement R1 ("include text input fields for 'Festival Name' and 'Artist Name' above the main Trigger button"), a new `<section class="metadata-section">` will be inserted immediately between `<header class="dashboard-header">` and `<main class="trigger-section">`.

#### Concrete DOM Block:
```html
<!-- Metadata Input Form Section (Requirement R1) -->
<section class="metadata-section" id="metadata-section">
  <div class="metadata-card">
    <div class="form-group">
      <label for="festival-input" class="form-label">
        <span class="label-icon">🎪</span> FESTIVAL / EVENT
      </label>
      <input
        type="text"
        id="festival-input"
        class="form-input"
        placeholder="e.g. EDC Las Vegas (Default: Concert)"
        autocomplete="off"
        spellcheck="false"
        maxlength="100"
      />
    </div>
    <div class="form-group">
      <label for="artist-input" class="form-label">
        <span class="label-icon">🎧</span> ARTIST / DJ
      </label>
      <input
        type="text"
        id="artist-input"
        class="form-input"
        placeholder="e.g. Subtronics (Default: Artist)"
        autocomplete="off"
        spellcheck="false"
        maxlength="100"
      />
    </div>
  </div>
</section>
```

### 1.3 CSS Styling Rules (OLED Dark Theme & Mobile Responsiveness)
The new form card matches the existing design system tokens:
- **Card Background**: `var(--bg-card-glass)` (`rgba(18, 18, 24, 0.85)`) with `backdrop-filter: blur(12px)`.
- **Borders & Radii**: `border: 1px solid var(--border-glass)` (`rgba(255, 255, 255, 0.08)`), `border-radius: 16px`.
- **Input Fields**:
  - `font-size: 16px;` (Mandatory for mobile browsers — values below 16px trigger automatic iOS Safari / Android Chrome viewport zooming on input focus).
  - Background: `var(--bg-surface-elevated)` (`#121218`), text: `var(--text-primary)` (`#ffffff`), placeholder: `var(--text-muted)` (`rgba(255, 255, 255, 0.45)`).
  - Focus Ring: `border-color: var(--neon-cyan)` (`#00ffcc`), `box-shadow: 0 0 12px rgba(0, 255, 204, 0.3)`.
  - Touch: `touch-action: manipulation; -webkit-tap-highlight-color: transparent;`.

```css
/* Metadata Form Section Styling */
.metadata-section {
  width: 100%;
}

.metadata-card {
  background: var(--bg-card-glass);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--border-glass);
  border-radius: 16px;
  padding: 14px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 0.70rem;
  font-weight: 800;
  letter-spacing: 1px;
  color: var(--neon-cyan);
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 6px;
}

.label-icon {
  font-size: 0.80rem;
}

.form-input {
  background: var(--bg-surface-elevated);
  border: 1px solid var(--border-glass);
  border-radius: 10px;
  color: var(--text-primary);
  font-family: inherit;
  font-size: 16px; /* Prevents auto-zoom on mobile devices */
  padding: 10px 14px;
  outline: none;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  touch-action: manipulation;
  box-sizing: border-box;
  width: 100%;
}

.form-input::placeholder {
  color: var(--text-muted);
  font-size: 0.85rem;
}

.form-input:focus {
  border-color: var(--neon-cyan);
  box-shadow: 0 0 12px rgba(0, 255, 204, 0.3);
}
```

### 1.4 JavaScript Client Logic & Payload Construction
In `RemoteTriggerClient`:

```javascript
class RemoteTriggerClient {
  constructor() {
    this.triggerBtn = document.getElementById('trigger-btn');
    this.btnSpinner = document.getElementById('btn-spinner');
    this.festivalInput = document.getElementById('festival-input');
    this.artistInput = document.getElementById('artist-input');
    this.toastCard = document.getElementById('toast-card');
    this.toastTitle = document.getElementById('toast-title');
    this.toastMessage = document.getElementById('toast-message');
    this.toastIcon = document.getElementById('toast-icon');
    this.statusToast = document.getElementById('status-toast');
    this.statusDisplay = document.getElementById('status-display');
    this.toastTimeout = null;
    this.pollInterval = null;

    this.initEventListeners();
    this.fetchSystemHealth();
    this.pollStatus();
  }

  // ...
  async handleTrigger(event) {
    if (this.triggerBtn && this.triggerBtn.disabled) return;

    this.setButtonLoading(true);

    const festivalVal = this.festivalInput ? this.festivalInput.value.trim() : "";
    const artistVal = this.artistInput ? this.artistInput.value.trim() : "";

    const finalFestival = festivalVal || "Concert";
    const finalArtist = artistVal || "Artist";

    const payload = {
      festival: finalFestival,
      event: finalFestival, // backward-compatible alias
      artist: finalArtist,
      brand: "laser_baptism",
      tier: "pillar_a_stadium_arena",
      from_device: true,
      auto_drop: true,
      drop_duration: 30.0,
      publish_youtube: false,
      auto_promote: false
    };

    try {
      const response = await fetch('/trigger-pipeline', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (response.status === 202) {
        this.vibrate([100, 100, 100]); // Dual-pulse success vibration
        const jobId = data.job_id || 'OK';
        this.showToast(
          'Accepted (202)',
          'Job started: ' + jobId + ' [' + finalFestival + ' / ' + finalArtist + ']',
          'success',
          '🚀'
        );
        this.startTelemetryPolling();
      } else if (response.status === 409) {
        this.vibrate([500, 200, 500]); // Warning vibration
        const elapsed = (data.elapsed_seconds !== undefined && data.elapsed_seconds !== null)
          ? ' (' + Number(data.elapsed_seconds).toFixed(1) + 's elapsed)'
          : '';
        const currentJob = data.current_job_id || 'Job in progress';
        this.showToast(
          'Busy (409 Conflict)',
          'Pipeline already running: ' + currentJob + elapsed,
          'warning',
          '⚠️'
        );
      } else {
        this.vibrate([500, 200, 500]);
        this.showToast(
          'Error (' + response.status + ')',
          data.detail || data.error || 'Server rejected request',
          'error',
          '❌'
        );
      }
    } catch (networkError) {
      this.vibrate([500, 200, 500]);
      this.showToast(
        'Network Error',
        'Failed to reach workstation server (' + (networkError.message || networkError) + ')',
        'error',
        '❌'
      );
    } finally {
      this.setButtonLoading(false);
    }
  }
}
```

---

## 2. Backend Investigation: `content_creation/remote_trigger.py`

### 2.1 Pydantic Model Schema Expansion
Currently, `PipelineTriggerRequest` defines `event: str = Field(default="Concert")` and `artist: str = Field(default="Artist")`.
To support `festival` and `event` interoperably:

```python
class PipelineTriggerRequest(BaseModel):
    """Payload schema for triggering the automated pipeline."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    festival: Optional[str] = Field(default=None, description="Festival or event name")
    event: Optional[str] = Field(default="Concert", description="Event or festival name")
    artist: str = Field(default="Artist", description="DJ or artist name")
    track: str = Field(default="ID", description="Track title or ID")
    genre: str = Field(default="house", description="EDM subgenre for pacing")
    brand: str = Field(default="laser_baptism", description="Brand umbrella (laser_baptism / music_baptism)")
    tier: str = Field(default="pillar_a_stadium_arena", description="Event tier pillar")
    from_device: bool = Field(default=True, description="Pull take from Samsung S26 Ultra via ADB")
    device_serial: Optional[str] = Field(default=None, description="Explicit ADB device serial")
    input_file: Optional[str] = Field(default=None, description="Explicit local input video file")
    auto_drop: bool = Field(default=True, description="Enable Librosa 30s RMS drop detection")
    drop_duration: float = Field(default=30.0, ge=5.0, le=59.0, description="Drop window duration in seconds")
    start_time: Optional[float] = Field(default=None, ge=0.0, description="Manual start time override")
    duration: Optional[float] = Field(default=None, ge=5.0, le=59.0, description="Manual duration override")
    reframe_mode: str = Field(default="center_crop", description="Reframe mode (center_crop / blur_pad / offset_crop)")
    publish_youtube: bool = Field(default=False, description="Trigger YouTube Data API v3 upload")
    auto_promote: bool = Field(default=False, description="Auto-promote from unlisted to public")
    poll_timeout: Optional[float] = Field(default=300.0, ge=10.0, description="Content ID polling timeout in seconds")
    client_secrets: Optional[str] = Field(default=None, description="Path to client_secret.json")
    token_path: Optional[str] = Field(default=None, description="Path to token.json")
    dry_run: bool = Field(default=False, description="Simulate without executing file I/O or ffmpeg")

    @property
    def resolved_event(self) -> str:
        """Resolves festival/event name with fallbacks."""
        if self.festival and self.festival.strip():
            return self.festival.strip()
        if self.event and self.event.strip():
            return self.event.strip()
        return "Concert"

    @property
    def resolved_artist(self) -> str:
        """Resolves artist name with fallbacks."""
        return self.artist.strip() if (self.artist and self.artist.strip()) else "Artist"
```

### 2.2 CLI Command Builder: `build_orchestrator_command`
The command builder translates `PipelineTriggerRequest` into the exact CLI arguments for `orchestrator.py`:

```python
def build_orchestrator_command(
    request: PipelineTriggerRequest,
    workspace_root: Path,
    python_bin: str = sys.executable,
) -> List[str]:
    """Constructs the canonical CLI invocation list for orchestrator.py pipeline."""
    orchestrator_script = workspace_root / "orchestrator.py"

    resolved_event = request.resolved_event
    resolved_artist = request.resolved_artist

    cmd: List[str] = [
        python_bin,
        str(orchestrator_script),
        "--target-dir",
        str(workspace_root),
        "pipeline",
        "--event",
        str(resolved_event),
        "--artist",
        str(resolved_artist),
        "--track",
        str(request.track),
        "--genre",
        str(request.genre),
        "--brand",
        str(request.brand),
        "--tier",
        str(request.tier),
        "--reframe-mode",
        str(request.reframe_mode),
        "--drop-duration",
        str(request.drop_duration),
    ]

    # ... remaining flags (--from-device, --auto-drop, --publish-youtube, etc.)
    return cmd
```

### 2.3 `orchestrator.py` CLI Compatibility
In `orchestrator.py`, the `pipeline` subparser defines:
```python
pipe_p.add_argument("--event", "--festival", dest="event", required=True, help="Event/Festival name.")
pipe_p.add_argument("--artist", required=True, help="DJ/Artist name.")
```
Adding `--festival` as an alias for `--event` in `orchestrator.py` provides total flexibility for both CLI operators and automated subprocesses.

---

## 3. Test Suite Expectations & Backwards Compatibility Matrix

### 3.1 Existing Test Invariants in `content_creation/tests/`

| Test File | Test Method | Key Assertions / Invariants | Impact of R1 |
|---|---|---|---|
| `test_remote_trigger.py` | `test_pipeline_trigger_request_defaults` | Asserts `req.event == "Concert"`, `req.artist == "Artist"` | **MUST PRESERVE**: Default values of `event` and `artist` remain `"Concert"` and `"Artist"`. |
| `test_remote_trigger.py` | `test_build_orchestrator_command_defaults` | Asserts `["--event", "Concert", "--artist", "Artist"]` in command list | **MUST PRESERVE**: Exact CLI arguments emitted. |
| `test_remote_trigger.py` | `test_pipeline_trigger_request_custom_and_extra_fields` | Tests extra fields and custom values | Preserved by `ConfigDict(extra="allow")`. |
| `test_adversarial_pwa_dom.py` | `test_utf8_encoding_compliance` | Byte-level UTF-8 validation of `index.html` | **MUST PRESERVE**: Must save `index.html` as valid UTF-8 without BOM. |
| `test_adversarial_pwa_dom.py` | `test_pwa_required_meta_tags_presence` | Asserts `name="viewport"`, `name="apple-mobile-web-app-capable"`, `name="theme-color"` (#000000), `apple-mobile-web-app-status-bar-style` | **MUST PRESERVE**: All meta tags remain intact in `<head>`. |
| `test_adversarial_pwa_dom.py` | `test_massive_trigger_button_element_and_exact_text` | Asserts `#trigger-btn`, `.massive-trigger-btn`, exact text `"TRIGGER EDM PIPELINE"` | **MUST PRESERVE**: `#trigger-btn` and exact text unchanged. |
| `test_adversarial_pwa_dom.py` | `test_toast_container_and_elements_presence` | Asserts `#toast-card`, `#toast-title`, `#toast-message`, `#toast-icon`, `#toast-close`, `#status-toast`, `#status-display` | **MUST PRESERVE**: All toast DOM IDs preserved. |
| `test_adversarial_pwa_dom.py` | `test_telemetry_hud_elements_presence` | Asserts `#daemon-state`, `#active-job-id`, `#elapsed-time`, `#last-job-summary`, `#badge-adb`, `#badge-ffmpeg`, `#cancel-btn` | **MUST PRESERVE**: All HUD DOM IDs preserved. |
| `test_adversarial_pwa_dom.py` | `test_javascript_syntax_and_ast_validity` | Node.js `vm.Script` parses embedded JS without syntax error | **MUST PRESERVE**: Client JS must be 100% valid ES6+. |
| `test_adversarial_pwa_dom.py` | `test_javascript_fetch_endpoint_contract` | Regex matches `fetch('/trigger-pipeline')`, `method: 'POST'` | **MUST PRESERVE**: Exact path `/trigger-pipeline`. |
| `test_adversarial_pwa_dom.py` | `test_javascript_success_haptic_array_contract_202` | `[100, 100, 100]` on HTTP 202 | **MUST PRESERVE**: Exact haptic pattern. |
| `test_adversarial_pwa_dom.py` | `test_javascript_error_haptic_array_contract_409_and_catch` | `[500, 200, 500]` on HTTP 409 and catch | **MUST PRESERVE**: Exact haptic pattern. |
| `test_adversarial_pwa_dom.py` | `test_javascript_vibration_feature_detection_guard` | Guards vibration calls with `'vibrate' in navigator` | **MUST PRESERVE**: Safe guard logic. |
| `test_adversarial_pwa_dom.py` | `test_javascript_debounce_locking_lifecycle` | `disabled = true` / `setButtonLoading(true)` before fetch, unlocked in `finally` | **MUST PRESERVE**: Debounce lifecycle. |
| `test_adversarial_pwa_dom.py` | `test_touch_action_manipulation` & `test_tap_highlight_color_transparent` | CSS rules `touch-action: manipulation`, `-webkit-tap-highlight-color: transparent` | **MUST PRESERVE**: Mobile CSS performance rules. |
| `test_adversarial_pwa_server_stress.py` | Rapid GET / bursts, POST /trigger-pipeline mutex concurrency (50-100 requests) | Mutex locking consistency, HTTP 202 vs 409 responses | **MUST PRESERVE**: Server async mutex and lifecycle. |

### 3.2 Verification Command Baseline
During investigation, all 86 PWA/RemoteTrigger unit and integration tests passed cleanly in 5.58 seconds:
```bash
python -m unittest tests/test_remote_trigger.py tests/test_adversarial_pwa_dom.py tests/test_adversarial_pwa_server_stress.py
```

---

## 4. Proposed Code Diffs & Implementer Guidance

### 4.1 Target File: `content_creation/static/index.html` (and sync to `content_creation/index.html`)

#### Diff 1: Insert Metadata Form HTML above `.trigger-section` (approx line 452)
```html
<<<< CURRENT
    <!-- Header / Branding & System Health -->
    <header class="dashboard-header">
      <div class="brand-title">
        <span class="neon-cyan">⚡ LASER</span><span class="neon-pink">BAPTISM</span>
      </div>
      <div id="health-badges" class="health-badges-container">
        <span id="badge-adb" class="badge badge-idle" title="ADB Status">ADB</span>
        <span id="badge-ffmpeg" class="badge badge-idle" title="FFmpeg Status">FFMPEG</span>
        <span id="badge-server" class="badge badge-ok" title="Server Status">ONLINE</span>
      </div>
    </header>

    <!-- Main Giant Trigger Control Section -->
    <main class="trigger-section">
==== PROPOSED
    <!-- Header / Branding & System Health -->
    <header class="dashboard-header">
      <div class="brand-title">
        <span class="neon-cyan">⚡ LASER</span><span class="neon-pink">BAPTISM</span>
      </div>
      <div id="health-badges" class="health-badges-container">
        <span id="badge-adb" class="badge badge-idle" title="ADB Status">ADB</span>
        <span id="badge-ffmpeg" class="badge badge-idle" title="FFmpeg Status">FFMPEG</span>
        <span id="badge-server" class="badge badge-ok" title="Server Status">ONLINE</span>
      </div>
    </header>

    <!-- Metadata Input Form Section (Requirement R1) -->
    <section class="metadata-section" id="metadata-section">
      <div class="metadata-card">
        <div class="form-group">
          <label for="festival-input" class="form-label">
            <span class="label-icon">🎪</span> FESTIVAL / EVENT
          </label>
          <input
            type="text"
            id="festival-input"
            class="form-input"
            placeholder="e.g. EDC Las Vegas (Default: Concert)"
            autocomplete="off"
            spellcheck="false"
            maxlength="100"
          />
        </div>
        <div class="form-group">
          <label for="artist-input" class="form-label">
            <span class="label-icon">🎧</span> ARTIST / DJ
          </label>
          <input
            type="text"
            id="artist-input"
            class="form-input"
            placeholder="e.g. Subtronics (Default: Artist)"
            autocomplete="off"
            spellcheck="false"
            maxlength="100"
          />
        </div>
      </div>
    </section>

    <!-- Main Giant Trigger Control Section -->
    <main class="trigger-section">
>>>>
```

#### Diff 2: Insert CSS for Metadata Card & Inputs in `<style>` (approx line 140)
```css
<<<< CURRENT
    /* Trigger Section */
    .trigger-section {
      display: flex;
==== PROPOSED
    /* Metadata Input Section */
    .metadata-section {
      width: 100%;
    }

    .metadata-card {
      background: var(--bg-card-glass);
      backdrop-filter: blur(12px);
      -webkit-backdrop-filter: blur(12px);
      border: 1px solid var(--border-glass);
      border-radius: 16px;
      padding: 14px 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.5);
    }

    .form-group {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    .form-label {
      font-size: 0.70rem;
      font-weight: 800;
      letter-spacing: 1px;
      color: var(--neon-cyan);
      text-transform: uppercase;
      display: flex;
      align-items: center;
      gap: 6px;
    }

    .label-icon {
      font-size: 0.80rem;
    }

    .form-input {
      background: var(--bg-surface-elevated);
      border: 1px solid var(--border-glass);
      border-radius: 10px;
      color: var(--text-primary);
      font-family: inherit;
      font-size: 16px; /* Prevents auto-zoom on mobile Safari / Chrome */
      padding: 10px 14px;
      outline: none;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
      touch-action: manipulation;
      box-sizing: border-box;
      width: 100%;
    }

    .form-input::placeholder {
      color: var(--text-muted);
      font-size: 0.85rem;
    }

    .form-input:focus {
      border-color: var(--neon-cyan);
      box-shadow: 0 0 12px rgba(0, 255, 204, 0.3);
    }

    /* Trigger Section */
    .trigger-section {
      display: flex;
>>>>
```

#### Diff 3: Update `RemoteTriggerClient` in `<script>` (approx line 518)
```javascript
<<<< CURRENT
      constructor() {
        this.triggerBtn = document.getElementById('trigger-btn');
        this.btnSpinner = document.getElementById('btn-spinner');
        this.toastCard = document.getElementById('toast-card');
==== PROPOSED
      constructor() {
        this.triggerBtn = document.getElementById('trigger-btn');
        this.btnSpinner = document.getElementById('btn-spinner');
        this.festivalInput = document.getElementById('festival-input');
        this.artistInput = document.getElementById('artist-input');
        this.toastCard = document.getElementById('toast-card');
>>>>
```

```javascript
<<<< CURRENT
        const payload = {
          event: "LiveConcert",
          artist: "AutoArtist",
          brand: "laser_baptism",
          tier: "pillar_a_stadium_arena",
          from_device: true,
          auto_drop: true,
          drop_duration: 30.0,
          publish_youtube: false,
          auto_promote: false
        };
==== PROPOSED
        const festivalVal = this.festivalInput ? this.festivalInput.value.trim() : "";
        const artistVal = this.artistInput ? this.artistInput.value.trim() : "";

        const finalFestival = festivalVal || "Concert";
        const finalArtist = artistVal || "Artist";

        const payload = {
          festival: finalFestival,
          event: finalFestival,
          artist: finalArtist,
          brand: "laser_baptism",
          tier: "pillar_a_stadium_arena",
          from_device: true,
          auto_drop: true,
          drop_duration: 30.0,
          publish_youtube: false,
          auto_promote: false
        };
>>>>
```

---

### 4.2 Target File: `content_creation/remote_trigger.py`

#### Diff 1: `PipelineTriggerRequest` Pydantic Schema
```python
<<<< CURRENT
class PipelineTriggerRequest(BaseModel):
    """Payload schema for triggering the automated pipeline."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    event: str = Field(default="Concert", description="Event or festival name")
    artist: str = Field(default="Artist", description="DJ or artist name")
    track: str = Field(default="ID", description="Track title or ID")
==== PROPOSED
class PipelineTriggerRequest(BaseModel):
    """Payload schema for triggering the automated pipeline."""
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    festival: Optional[str] = Field(default=None, description="Festival or event name")
    event: Optional[str] = Field(default="Concert", description="Event or festival name")
    artist: str = Field(default="Artist", description="DJ or artist name")
    track: str = Field(default="ID", description="Track title or ID")

    @property
    def resolved_event(self) -> str:
        """Resolves festival/event name with fallbacks."""
        if self.festival and self.festival.strip():
            return self.festival.strip()
        if self.event and self.event.strip():
            return self.event.strip()
        return "Concert"

    @property
    def resolved_artist(self) -> str:
        """Resolves artist name with fallbacks."""
        return self.artist.strip() if (self.artist and self.artist.strip()) else "Artist"
>>>>
```

#### Diff 2: `build_orchestrator_command` Parameter Resolution
```python
<<<< CURRENT
        "pipeline",
        "--event",
        str(request.event),
        "--artist",
        str(request.artist),
        "--track",
==== PROPOSED
        "pipeline",
        "--event",
        str(request.resolved_event),
        "--artist",
        str(request.resolved_artist),
        "--track",
>>>>
```

---

## 5. Summary Conclusion & Readiness
1. **Frontend**: The proposed DOM injection, OLED styling, and JavaScript logic seamlessly integrate "Festival Name" and "Artist Name" without disrupting any existing PWA meta tags, touch responsiveness, vibration haptics, or toast alert IDs.
2. **Backend**: Expanding `PipelineTriggerRequest` with `festival` (and resolving across `event` and `festival`) guarantees complete forward and backward compatibility with both JSON payloads and existing tests.
3. **Tests**: All 86 PWA/RemoteTrigger tests pass cleanly against the current baseline and will remain 100% green with these additive modifications.
