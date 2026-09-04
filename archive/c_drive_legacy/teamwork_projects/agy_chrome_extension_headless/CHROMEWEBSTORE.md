# Chrome Web Store Listing — Antigravity Universal Agent (Headless)

> Last Updated: 2026-08-24

## Store Listing

**Extension Name** [REQUIRED]
Antigravity Universal Agent (Headless)

**Short Description** [REQUIRED]
Pure headless Manifest V3 background service worker for secure omnichannel messaging and capture coordination.

**Detailed Description** [REQUIRED]
Antigravity Universal Agent (Headless) is a lightweight, secure Manifest V3 background service worker designed for seamless developer automation and cross-application message passing.

Key Features
Pure background operation with zero intrusive UI popups or side panels.
Deterministic external messaging interface via chrome.runtime.onMessageExternal.
Bi-directional local WebSocket communication for seamless local agent orchestration.
Zero DOM scraping or dynamic code evaluation for maximum security and compliance with modern browser CSP standards.
High performance tab metadata coordination without main thread blocking.

How to Use
1. Install and enable the extension.
2. The extension automatically runs silently in the background as a Manifest V3 service worker.
3. Connect your local automation workflow via WebSocket (ws://localhost:8002/ws) or cross-origin extension messaging.

Privacy and Security
This extension does not collect, track, or transmit your personal data, browser history, or page content. It operates strictly as a local-first message passer.

Support and Feedback
For technical documentation, issue tracking, and contributions, visit the Antigravity developer repository.

**Category** [REQUIRED]
Developer Tools

**Single Purpose** [REQUIRED]
Provides a headless Manifest V3 background message passing interface between local developer tools and Chrome tabs.

**Primary Language** [REQUIRED]
English

---

## Graphics & Assets

| Asset | Dimensions | Status | Filename |
|-------|-----------|--------|----------|
| Store Icon [REQUIRED] | 128×128 PNG | ⬜ Not created | |
| Screenshot 1 [REQUIRED] | 1280×800 or 640×400 | ⬜ Not created | |
| Screenshot 2 [RECOMMENDED] | 1280×800 or 640×400 | ⬜ Not created | |
| Small Promo Tile [RECOMMENDED] | 440×280 | ⬜ Not created | |
| Marquee Promo Tile | 1400×560 | ⬜ Not created | |

### Screenshot Notes
Screenshot 1: Visual diagram showing the headless architecture and local WebSocket message passing flow between the agent and service worker.

---

## Permissions Justification

| Permission | Type | Justification |
|------------|------|---------------|
| `storage` | permissions | Used to persist configuration state and session parameters across service worker restarts. |
| `tabs` | permissions | Used to retrieve tab identifiers and URLs for coordinating external capture triggers requested by the local automation agent. |
| `alarms` | permissions | Used for periodic service worker health checks, keepalive triggers, and background daemon reconnection without relying on ephemeral in-memory timers. |
| `*://localhost/*` | externally_connectable | Allows local web applications on localhost to communicate with the extension service worker. |
| `*://127.0.0.1/*` | externally_connectable | Allows local automation scripts running on loopback IP to communicate with the extension service worker. |

---

## Privacy & Data Use

### Data Collection

**Does the extension collect user data?** No

### Data Use Certification
- [x] Data is NOT sold to third parties
- [x] Data is NOT used for purposes unrelated to the extension's core functionality
- [x] Data is NOT used for creditworthiness or lending purposes

---

## Privacy Policy

**Privacy Policy URL** [RECOMMENDED]
https://github.com/antigravity/privacy-policy

---

## Distribution

**Visibility**: Unlisted
**Regions**: All regions
**Pricing**: Free

---

## Developer Info

**Publisher Name** [REQUIRED]
Antigravity Core Engineering

**Contact Email** [REQUIRED]
developer@antigravity.local

**Support URL / Email** [RECOMMENDED]
https://github.com/antigravity/support

**Homepage URL** [RECOMMENDED]
https://github.com/antigravity

---

## Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| 1.0.0 | 2026-08-24 | Initial release: pure headless Manifest V3 background service worker with zero UI and secure message passing. | Draft |

---

## Review Notes

### Known Issues / Limitations
The extension is fully headless and does not render any browser popup or action menu.
