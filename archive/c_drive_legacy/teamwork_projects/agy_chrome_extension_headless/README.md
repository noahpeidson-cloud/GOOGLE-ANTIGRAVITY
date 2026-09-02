# Antigravity Headless Chrome Extension (Manifest V3)

A pure headless Manifest V3 background service worker for omnichannel messaging and capture coordination.

## Architecture

```
+-----------------------------+               +--------------------------------------+
|  Local Python Agent Daemon  | <== [WS] ===> | Chrome Extension Service Worker     |
|  (ws://localhost:8002/ws)   |               | (background.js - MV3 Headless)       |
+-----------------------------+               +--------------------------------------+
                                                                 ^
                                                                 | [chrome.runtime.onMessageExternal]
                                                                 v
                                              +--------------------------------------+
                                              | Web Apps / External Callers          |
                                              | (*://localhost/*, *://127.0.0.1/*)   |
                                              +--------------------------------------+
                                                                 ^
                                                                 | [Native Messaging Host]
                                                                 v
                                              +--------------------------------------+
                                              | Python Native Host (stdio bridge)    |
                                              | (com.antigravity.headless.agent)     |
                                              +--------------------------------------+
```

### Key Principles
1. **Pure Message Passer**: The extension performs zero DOM scraping, DOM traversal, or dynamic evaluation (`eval()`). Actual extraction is handled externally by the Python MCP agent via the Chrome DevTools MCP Accessibility Tree.
2. **Headless & Silent**: No popup UI (`default_popup`), no sidepanel UI (`sidepanel.html`), no content scripts.
3. **Manifest V3 Compliant**: Uses background service worker (`background.js`), standard MV3 permissions (`storage`, `tabs`, `alarms`), and compliant `externally_connectable` match patterns.
4. **Resilient Ephemeral Lifecycle**: Utilizes `chrome.alarms` and event-driven wake-up patterns so the service worker gracefully wakes up from sleep and restores daemon communication.

---

## Messaging Interface

### External Messaging (`chrome.runtime.onMessageExternal`)

#### 1. PING Request
```json
{
  "type": "PING",
  "id": "req-001"
}
```
**Response**:
```json
{
  "status": "ok",
  "type": "PONG",
  "version": "1.0.0",
  "id": "req-001",
  "headless": true,
  "timestamp": 1724567890000
}
```

#### 2. CAPTURE_TRIGGER Request
```json
{
  "type": "CAPTURE_TRIGGER",
  "target": "tab-123",
  "url": "https://example.com"
}
```
**Response**:
```json
{
  "status": "ok",
  "action": "capture_triggered",
  "proxy": true,
  "wsForwarded": true,
  "target": "tab-123",
  "url": "https://example.com",
  "timestamp": 1724567890000
}
```

#### 3. GET_STATUS Request
```json
{
  "type": "GET_STATUS"
}
```
**Response**:
```json
{
  "status": "ok",
  "service_worker": "active",
  "headless": true,
  "version": "1.0.0",
  "wsConnected": true,
  "timestamp": 1724567890000
}
```

#### 4. GET_ACTIVE_TAB Request
```json
{
  "type": "GET_ACTIVE_TAB"
}
```
**Response**:
```json
{
  "status": "ok",
  "action": "active_tab",
  "tab": {
    "id": 101,
    "url": "https://example.com",
    "title": "Example Domain",
    "windowId": 1,
    "active": true,
    "status": "complete"
  },
  "timestamp": 1724567890000
}
```

#### 5. QUERY_TABS Request
```json
{
  "type": "QUERY_TABS",
  "query": { "active": true }
}
```
**Response**:
```json
{
  "status": "ok",
  "action": "query_tabs",
  "tabs": [
    {
      "id": 101,
      "url": "https://example.com",
      "title": "Example Domain",
      "windowId": 1,
      "active": true,
      "status": "complete"
    }
  ],
  "timestamp": 1724567890000
}
```

---

## WebSocket Daemon Interface (`ws://localhost:8002/ws`)

- **Ready Handshake**: Extension sends `{ "type": "READY", "version": "1.0.0", "headless": true }` on connection.
- **Daemon Ping**: Extension responds to `{ "type": "PING", "id": "..." }` with `{ "type": "PONG", "id": "...", "status": "acknowledged", "headless": true }`.
- **Capture Trigger**: Extension responds to `{ "type": "CAPTURE_TRIGGER", "id": "..." }` with `{ "type": "CAPTURE_TRIGGER_ACK", "id": "...", "status": "acknowledged", "proxy": true }`.
- **Status Query**: Extension responds to `{ "type": "GET_STATUS", "id": "..." }` with `{ "type": "STATUS_RESPONSE", "id": "...", "status": "ok", "service_worker": "active", "headless": true }`.
- **Active Tab Query**: Extension responds to `{ "type": "GET_ACTIVE_TAB", "id": "..." }` with `{ "type": "ACTIVE_TAB_RESPONSE", "id": "...", "status": "ok", "tab": { ... } }`.
- **Query Tabs**: Extension responds to `{ "type": "QUERY_TABS", "id": "...", "query": {} }` with `{ "type": "QUERY_TABS_RESPONSE", "id": "...", "status": "ok", "tabs": [...] }`.
- **Echo**: Extension responds to `{ "type": "ECHO", "id": "...", "payload": { ... } }` with `{ "type": "ECHO_RESPONSE", "id": "...", "status": "ok", "payload": { ... } }`.

---

## Native Messaging Host Specification

For native messaging setups without WebSocket servers, the extension supports communication with `com.antigravity.headless.agent`.

### Native Host Manifest (`com.antigravity.headless.agent.json`)
```json
{
  "name": "com.antigravity.headless.agent",
  "description": "Antigravity Headless Python Native Host",
  "path": "host.bat",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://<EXTENSION_ID>/"
  ]
}
```

---

## Verification & Testing

Run the comprehensive integration test suite with pytest:
```bash
python -m pytest test_messaging.py -v
```
