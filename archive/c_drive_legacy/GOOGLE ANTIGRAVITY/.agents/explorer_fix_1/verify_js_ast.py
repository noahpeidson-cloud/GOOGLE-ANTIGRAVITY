import os
import subprocess
import sys
import tempfile

js_code = """
class RemoteTriggerClient {
  constructor() {
    this.triggerBtn = document.getElementById("trigger-btn");
    this.btnSpinner = document.getElementById("btn-spinner");
    this.toastCard = document.getElementById("toast-card");
    this.toastTitle = document.getElementById("toast-title");
    this.toastMessage = document.getElementById("toast-message");
    this.toastIcon = document.getElementById("toast-icon");
    this.statusToast = document.getElementById("status-toast");
    this.statusDisplay = document.getElementById("status-display");
    this.toastTimeout = null;
    this.pollInterval = null;

    this.initEventListeners();
    this.fetchSystemHealth();
    this.pollStatus();
  }

  initEventListeners() {
    this.triggerBtn?.addEventListener("click", (e) => this.handleTrigger(e));
    document.getElementById("toast-close")?.addEventListener("click", () => this.hideToast());
    document.getElementById("refresh-status-btn")?.addEventListener("click", () => this.pollStatus());
    document.getElementById("cancel-btn")?.addEventListener("click", () => this.handleCancel());
    window.addEventListener("online", () => this.showToast("Online", "Connected to network", "success", "⚡"));
    window.addEventListener("offline", () => {
      this.vibrate([500, 200, 500]);
      this.showToast("Offline", "No Wi-Fi / LAN connection", "error", "⚠️");
    });
  }

  vibrate(pattern) {
    try {
      if ("vibrate" in navigator && typeof navigator.vibrate === "function") {
        navigator.vibrate(pattern);
      }
    } catch (err) {
      console.warn("[Haptics] navigator.vibrate failed or blocked:", err);
    }
  }

  async handleTrigger(event) {
    if (this.triggerBtn && this.triggerBtn.disabled) return;
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
      const response = await fetch("/trigger-pipeline", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Accept": "application/json"
        },
        body: JSON.stringify(payload)
      });

      const data = await response.json();

      if (response.status === 202) {
        this.vibrate([100, 100, 100]);
        const jobId = data.job_id || "OK";
        this.showToast("Accepted (202)", "Job started: " + jobId, "success", "🚀");
        this.startTelemetryPolling();
      } else if (response.status === 409) {
        this.vibrate([500, 200, 500]);
        const elapsed = (data.elapsed_seconds !== undefined && data.elapsed_seconds !== null)
          ? " (" + Number(data.elapsed_seconds).toFixed(1) + "s elapsed)"
          : "";
        const currentJob = data.current_job_id || "Job in progress";
        this.showToast("Busy (409 Conflict)", "Pipeline already running: " + currentJob + elapsed, "warning", "⚠️");
      } else {
        this.vibrate([500, 200, 500]);
        this.showToast("Error (" + response.status + ")", data.detail || data.error || "Server rejected request", "error", "❌");
      }
    } catch (networkError) {
      this.vibrate([500, 200, 500]);
      this.showToast("Network Error", "Failed to reach workstation server (" + (networkError.message || networkError) + ")", "error", "❌");
    } finally {
      this.setButtonLoading(false);
    }
  }

  setButtonLoading(isLoading) {
    if (!this.triggerBtn) return;
    this.triggerBtn.disabled = isLoading;
    if (isLoading) {
      this.btnSpinner?.classList.remove("hidden");
      this.triggerBtn.setAttribute("aria-busy", "true");
    } else {
      this.btnSpinner?.classList.add("hidden");
      this.triggerBtn.removeAttribute("aria-busy");
    }
  }

  showToast(title, message, type, icon) {
    type = type || "success";
    icon = icon || "🚀";
    if (this.toastTimeout) clearTimeout(this.toastTimeout);

    if (this.toastTitle) this.toastTitle.textContent = title;
    if (this.toastMessage) this.toastMessage.textContent = message;
    if (this.toastIcon) this.toastIcon.textContent = icon;

    if (this.statusToast) {
      this.statusToast.textContent = title + ": " + message;
    }
    if (this.statusDisplay) {
      this.statusDisplay.textContent = title + ": " + message;
    }

    if (this.toastCard) {
      this.toastCard.className = "toast-card toast-" + type;
      this.toastCard.classList.remove("hidden");
    }

    this.toastTimeout = setTimeout(() => {
      this.hideToast();
    }, 4500);
  }

  hideToast() {
    if (this.toastCard) {
      this.toastCard.classList.add("hidden");
    }
  }

  async pollStatus() {
    try {
      const res = await fetch("/status");
      if (!res.ok) return;
      const statusData = await res.json();
      this.updateTelemetryDOM(statusData);
    } catch (e) {
      console.debug("[Telemetry] Status poll failed:", e);
    }
  }

  updateTelemetryDOM(status) {
    const stateEl = document.getElementById("daemon-state");
    const jobEl = document.getElementById("active-job-id");
    const elapsedEl = document.getElementById("elapsed-time");
    const cancelBtn = document.getElementById("cancel-btn");
    const lastEl = document.getElementById("last-job-summary");

    if (stateEl) {
      const st = (status.state || "IDLE").toUpperCase();
      stateEl.textContent = st;
      stateEl.className = "state-pill state-" + st.toLowerCase();
    }
    if (jobEl) {
      jobEl.textContent = status.current_job_id || "None";
    }
    if (elapsedEl) {
      const elapsed = status.active_job?.elapsed_seconds || 0.0;
      elapsedEl.textContent = Number(elapsed).toFixed(1) + "s";
    }
    if (lastEl && status.last_job) {
      const lastId = status.last_job.job_id || "unknown";
      const lastState = status.last_job.state || "UNKNOWN";
      lastEl.textContent = lastId + " (" + lastState + ")";
    }
    if (cancelBtn) {
      if (status.is_running) {
        cancelBtn.classList.remove("hidden");
      } else {
        cancelBtn.classList.add("hidden");
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
      const res = await fetch("/cancel", { method: "POST" });
      const data = await res.json();
      if (res.ok) {
        this.vibrate([100, 100, 100]);
        this.showToast("Cancelled", data.message || "Pipeline aborted", "warning", "⚠️");
        this.pollStatus();
      } else {
        this.showToast("Error", data.detail || "Cancel failed", "error", "❌");
      }
    } catch (err) {
      this.showToast("Error", "Cancel request failed: " + (err.message || err), "error", "❌");
    }
  }

  async fetchSystemHealth() {
    try {
      const res = await fetch("/health");
      if (!res.ok) return;
      const h = await res.json();
      const adbBadge = document.getElementById("badge-adb");
      const ffBadge = document.getElementById("badge-ffmpeg");

      if (adbBadge) {
        const adbOk = h.adb_connected || h.adb_status === "ok" || h.adb === true;
        adbBadge.className = "badge " + (adbOk ? "badge-ok" : "badge-err");
      }
      if (ffBadge) {
        const ffOk = h.ffmpeg_installed || h.ffmpeg_status === "ok" || h.ffmpeg === true;
        ffBadge.className = "badge " + (ffOk ? "badge-ok" : "badge-err");
      }
    } catch (e) {
      console.debug("[Health] Health probe failed:", e);
    }
  }
}

document.addEventListener("DOMContentLoaded", () => {
  window.remoteTriggerClient = new RemoteTriggerClient();
});
"""

node_runner = """
const vm = require("vm");
const fs = require("fs");
const code = fs.readFileSync(process.argv[2], "utf-8");
try {
  new vm.Script(code, { filename: "test_clean.js" });
  console.log("ES6_AST_PARSED_SUCCESSFULLY");
  process.exit(0);
} catch (err) {
  console.error("SYNTAX_ERROR:", err.message);
  process.exit(1);
}
"""

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf_js:
    tf_js.write(js_code)
    js_path = tf_js.name

with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf_node:
    tf_node.write(node_runner)
    node_path = tf_node.name

try:
    res = subprocess.run(["node", node_path, js_path], capture_output=True, text=True)
    print("Node Result:", res.stdout.strip())
    if res.stderr:
        print("Node Stderr:", res.stderr.strip())
    if res.returncode != 0:
        sys.exit(1)
finally:
    if os.path.exists(js_path):
        os.remove(js_path)
    if os.path.exists(node_path):
        os.remove(node_path)
