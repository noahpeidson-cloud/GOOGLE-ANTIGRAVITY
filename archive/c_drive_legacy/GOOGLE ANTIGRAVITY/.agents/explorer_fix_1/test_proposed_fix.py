import re
import subprocess
import tempfile
from pathlib import Path
from html.parser import HTMLParser

class DOMInspector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.all_ids = []
        self.scripts = []
        self.styles = []
        self._tag = None

    def handle_starttag(self, tag, attrs):
        self._tag = tag
        attr_map = dict(attrs)
        if 'id' in attr_map:
            self.all_ids.append(attr_map['id'])

    def handle_endtag(self, tag):
        self._tag = None

    def handle_data(self, data):
        if self._tag == 'script':
            self.scripts.append(data)
        elif self._tag == 'style':
            self.styles.append(data)

# Read current static/index.html
index_path = Path("G:/My Drive/GOOGLE ANTIGRAVITY/content_creation/static/index.html")
with open(index_path, "rb") as f:
    raw = f.read()

# Replace byte 0xd7 with &times;
raw_fixed = raw.replace(b"\xd7", b"&times;")

# Let's see if UTF-8 decodes cleanly
decoded = raw_fixed.decode("utf-8")
print("UTF-8 Decode:", "PASS" if len(decoded) > 0 else "FAIL")

# Now let's test replacing the script block with the clean script
clean_script = """
    /**
     * EDM Master Mind PWA Remote Trigger Engine
     * Handles async fetch dispatch, dual-branch vibration haptics, and live DOM toasts.
     */
    class RemoteTriggerClient {
      constructor() {
        this.triggerBtn = document.getElementById('trigger-btn');
        this.btnSpinner = document.getElementById('btn-spinner');
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

      initEventListeners() {
        // Primary trigger tap
        this.triggerBtn?.addEventListener('click', (e) => this.handleTrigger(e));

        // Manual toast close
        document.getElementById('toast-close')?.addEventListener('click', () => this.hideToast());

        // Status refresh button
        document.getElementById('refresh-status-btn')?.addEventListener('click', () => this.pollStatus());

        // Cancel active job button
        document.getElementById('cancel-btn')?.addEventListener('click', () => this.handleCancel());

        // Network online/offline indicators
        window.addEventListener('online', () => this.showToast('Online', 'Connected to network', 'success', '⚡'));
        window.addEventListener('offline', () => {
          this.vibrate([500, 200, 500]);
          this.showToast('Offline', 'No Wi-Fi / LAN connection', 'error', '⚠️');
        });
      }

      /**
       * Safe Haptic Vibration Execution with Browser Feature Detection
       * @param {number[]} pattern - Millisecond array [vibrate, pause, vibrate]
       */
      vibrate(pattern) {
        try {
          if ('vibrate' in navigator && typeof navigator.vibrate === 'function') {
            navigator.vibrate(pattern);
          }
        } catch (err) {
          console.warn('[Haptics] navigator.vibrate failed or blocked:', err);
        }
      }

      /**
       * Dispatches POST /trigger-pipeline
       */
      async handleTrigger(event) {
        if (this.triggerBtn && this.triggerBtn.disabled) return;

        // Debounce lock: disable button during in-flight dispatch
        this.setButtonLoading(true);

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
            // SUCCESS: HTTP 202 Accepted (<50ms)
            this.vibrate([100, 100, 100]); // Dual-pulse success vibration
            const jobId = data.job_id || 'OK';
            this.showToast(
              'Accepted (202)',
              'Job started: ' + jobId,
              'success',
              '🚀'
            );
            this.startTelemetryPolling();
          } else if (response.status === 409) {
            // CONFLICT: HTTP 409 Conflict (Job already running)
            this.vibrate([500, 200, 500]); // Heavy warning vibration
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
            // OTHER HTTP ERROR
            this.vibrate([500, 200, 500]);
            this.showToast(
              'Error (' + response.status + ')',
              data.detail || data.error || 'Server rejected request',
              'error',
              '❌'
            );
          }
        } catch (networkError) {
          // NETWORK / CONNECTION FAILURE
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

      setButtonLoading(isLoading) {
        if (!this.triggerBtn) return;
        this.triggerBtn.disabled = isLoading;
        if (isLoading) {
          this.btnSpinner?.classList.remove('hidden');
          this.triggerBtn.setAttribute('aria-busy', 'true');
        } else {
          this.btnSpinner?.classList.add('hidden');
          this.triggerBtn.removeAttribute('aria-busy');
        }
      }

      showToast(title, message, type = 'success', icon = '🚀') {
        if (this.toastTimeout) clearTimeout(this.toastTimeout);

        if (this.toastTitle) this.toastTitle.textContent = title;
        if (this.toastMessage) this.toastMessage.textContent = message;
        if (this.toastIcon) this.toastIcon.textContent = icon;

        if (this.statusToast) {
          this.statusToast.textContent = title + ': ' + message;
        }
        if (this.statusDisplay) {
          this.statusDisplay.textContent = title + ': ' + message;
        }

        if (this.toastCard) {
          this.toastCard.className = 'toast-card toast-' + type;
          this.toastCard.classList.remove('hidden');
        }

        // Auto-dismiss after 4.5 seconds
        this.toastTimeout = setTimeout(() => {
          this.hideToast();
        }, 4500);
      }

      hideToast() {
        if (this.toastCard) {
          this.toastCard.classList.add('hidden');
        }
      }

      async pollStatus() {
        try {
          const res = await fetch('/status');
          if (!res.ok) return;
          const statusData = await res.json();
          this.updateTelemetryDOM(statusData);
        } catch (e) {
          console.debug('[Telemetry] Status poll failed:', e);
        }
      }

      updateTelemetryDOM(status) {
        const stateEl = document.getElementById('daemon-state');
        const jobEl = document.getElementById('active-job-id');
        const elapsedEl = document.getElementById('elapsed-time');
        const cancelBtn = document.getElementById('cancel-btn');
        const lastEl = document.getElementById('last-job-summary');

        if (stateEl) {
          const st = (status.state || 'IDLE').toUpperCase();
          stateEl.textContent = st;
          stateEl.className = 'state-pill state-' + st.toLowerCase();
        }
        if (jobEl) {
          jobEl.textContent = status.current_job_id || 'None';
        }
        if (elapsedEl) {
          const elapsed = status.active_job?.elapsed_seconds || 0.0;
          elapsedEl.textContent = Number(elapsed).toFixed(1) + 's';
        }
        if (lastEl && status.last_job) {
          const lastId = status.last_job.job_id || 'unknown';
          const lastState = status.last_job.state || 'UNKNOWN';
          lastEl.textContent = lastId + ' (' + lastState + ')';
        }
        if (cancelBtn) {
          if (status.is_running) {
            cancelBtn.classList.remove('hidden');
          } else {
            cancelBtn.classList.add('hidden');
          }
        }
      }

      startTelemetryPolling() {
        if (this.pollInterval) clearInterval(this.pollInterval);
        this.pollInterval = setInterval(async () => {
          await this.pollStatus();
        }, 2000);
      }

      async handleCancel() {
        try {
          const res = await fetch('/cancel', { method: 'POST' });
          const data = await res.json();
          if (res.ok) {
            this.vibrate([100, 100, 100]);
            this.showToast('Cancelled', data.message || 'Pipeline aborted', 'warning', '⚠️');
            this.pollStatus();
          } else {
            this.showToast('Error', data.detail || 'Cancel failed', 'error', '❌');
          }
        } catch (err) {
          this.showToast('Error', 'Cancel request failed: ' + (err.message || err), 'error', '❌');
        }
      }

      async fetchSystemHealth() {
        try {
          const res = await fetch('/health');
          if (!res.ok) return;
          const h = await res.json();
          const adbBadge = document.getElementById('badge-adb');
          const ffBadge = document.getElementById('badge-ffmpeg');

          if (adbBadge) {
            const adbOk = h.adb_connected || h.adb_status === 'ok' || h.adb === true;
            adbBadge.className = 'badge ' + (adbOk ? 'badge-ok' : 'badge-err');
          }
          if (ffBadge) {
            const ffOk = h.ffmpeg_installed || h.ffmpeg_status === 'ok' || h.ffmpeg === true;
            ffBadge.className = 'badge ' + (ffOk ? 'badge-ok' : 'badge-err');
          }
        } catch (e) {
          console.debug('[Health] Health probe failed:', e);
        }
      }
    }

    // Instantiate on DOMContentLoaded
    document.addEventListener('DOMContentLoaded', () => {
      window.remoteTriggerClient = new RemoteTriggerClient();
    });
"""

full_html = re.sub(r"<script>[\s\S]*?</script>", f"<script>{clean_script}  </script>", decoded)

# Test AST on the full HTML script extraction
match = re.search(r"<script>([\s\S]*?)</script>", full_html)
extracted_script = match.group(1)

node_runner = """
const vm = require("vm");
const fs = require("fs");
const code = fs.readFileSync(process.argv[2], "utf-8");
try {
  new vm.Script(code, { filename: "extracted.js" });
  console.log("AST_CHECK: PASS");
  process.exit(0);
} catch (err) {
  console.error("AST_CHECK: FAIL -", err.message);
  process.exit(1);
}
"""

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf_js:
    tf_js.write(extracted_script)
    js_path = tf_js.name

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf_node:
    tf_node.write(node_runner)
    node_path = tf_node.name

res = subprocess.run(["node", node_path, js_path], capture_output=True, text=True)
print(res.stdout.strip())

# Check regex assertions
print("Fetch endpoint match:", bool(re.search(r"fetch\(\s*['\"]/trigger-pipeline['\"]", extracted_script)))
print("Fetch method POST match:", bool(re.search(r"method\s*:\s*['\"]POST['\"]", extracted_script)))
print("202 vibrate pattern match:", bool(re.search(r"202[\s\S]{1,200}?vibrate\(\s*\[100,\s*100,\s*100\]\s*\)", extracted_script)))
print("409 vibrate pattern match:", bool(re.search(r"409[\s\S]{1,200}?vibrate\(\s*\[500,\s*200,\s*500\]\s*\)", extracted_script)))
print("Feature detection guard match:", bool("'vibrate' in navigator" in extracted_script))
print("Debounce lock regex match:", bool(re.search(r"(this\.triggerBtn\.disabled\s*=\s*true|setButtonLoading\(\s*true\s*\))", extracted_script)))
print("Debounce unlock in finally match:", bool(re.search(r"finally\s*\{[\s\S]*?(this\.triggerBtn\.disabled\s*=\s*false|setButtonLoading\(\s*false\s*\))", extracted_script)))

dom = DOMInspector()
dom.feed(full_html)
print("Trigger button ID in DOM:", "trigger-btn" in dom.all_ids)
print("Toast card ID in DOM:", "toast-card" in dom.all_ids)
print("Toast title ID in DOM:", "toast-title" in dom.all_ids)
print("Toast message ID in DOM:", "toast-message" in dom.all_ids)
print("Status toast alias in DOM:", "status-toast" in dom.all_ids)
print("Status display alias in DOM:", "status-display" in dom.all_ids)
