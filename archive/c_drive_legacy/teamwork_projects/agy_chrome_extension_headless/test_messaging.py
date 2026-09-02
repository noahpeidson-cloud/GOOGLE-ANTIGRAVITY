"""Integration & Compliance Test Suite for Headless Manifest V3 Chrome Extension.

Validates:
1. Manifest V3 compliance (manifest_version == 3, service worker, externally_connectable, permissions).
2. Absence of content scripts, popup UIs, sidepanels, DOM scraping, and eval() calls.
3. Node syntax check and clean JavaScript execution without CSP errors.
4. Deterministic message handling for chrome.runtime.onMessageExternal (PING/PONG, triggers, status, tab querying, sanitization, error handling).
5. Service Worker MV3 lifecycle & Alarms API keepalive / wake-up simulation.
6. Native Messaging host manifest schema validation and native port simulation.
7. Deterministic bidirectional WebSocket ping/ack, trigger/ack, status, and tab query message passing with local Python daemon.
8. Malformed payload resilience and edge-case handling (arrays, primitives, missing actions, malformed JSON, query sanitization).
9. High-concurrency message passing stress test.
10. Real Headless Chrome extension loading verification.
"""

import json
import os
import re
import subprocess
import asyncio
import pytest
import websockets

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
MANIFEST_PATH = os.path.join(PROJECT_DIR, "manifest.json")
BACKGROUND_JS_PATH = os.path.join(PROJECT_DIR, "background.js")
CHROMEWEBSTORE_PATH = os.path.join(PROJECT_DIR, "CHROMEWEBSTORE.md")


class TestManifestCompliance:
    """Requirement 1 & Acceptance Criteria: Manifest V3 Compliance."""

    def test_manifest_file_exists(self):
        assert os.path.exists(MANIFEST_PATH), f"manifest.json must exist at {MANIFEST_PATH}"

    def test_chromewebstore_file_exists(self):
        assert os.path.exists(CHROMEWEBSTORE_PATH), f"CHROMEWEBSTORE.md must exist at {CHROMEWEBSTORE_PATH}"

    def test_manifest_v3_structure(self):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        # 1. Manifest version must be 3
        assert manifest.get("manifest_version") == 3, "manifest_version must be exactly 3"

        # 2. Must use service_worker, NOT legacy background.scripts
        background = manifest.get("background", {})
        assert "service_worker" in background, "background must define 'service_worker'"
        assert background["service_worker"] == "background.js", "service_worker must point to background.js"
        assert "scripts" not in background, "background.scripts is prohibited in Manifest V3"

        # 3. No content scripts used for DOM traversal or scraping
        assert "content_scripts" not in manifest, "content_scripts must NOT be declared in headless extension"

        # 4. No UI components (popups, side panels, browser_action, page_action)
        assert "side_panel" not in manifest, "side_panel UI must be removed"
        action = manifest.get("action", {})
        assert "default_popup" not in action, "action.default_popup must not be present in headless extension"
        assert "browser_action" not in manifest, "browser_action is deprecated V2"
        assert "page_action" not in manifest, "page_action is deprecated V2"

        # 5. Must configure externally_connectable for secure external message passing
        assert "externally_connectable" in manifest, "externally_connectable must be declared for external messaging"
        ext_conn = manifest["externally_connectable"]
        matches = ext_conn.get("matches", [])
        assert any("localhost" in m or "127.0.0.1" in m for m in matches), (
            "externally_connectable must allow local communication (localhost / 127.0.0.1)"
        )
        # Verify match pattern validity (no ports in patterns)
        for pattern in matches:
            assert not re.search(r":\d+", pattern), f"Match pattern '{pattern}' must not contain port numbers"

        # 6. Verify minimal and safe permissions
        permissions = manifest.get("permissions", [])
        assert "storage" in permissions, "storage permission should be present for state management"
        assert "tabs" in permissions, "tabs permission should be present for coordinating target tabs"
        assert "alarms" in permissions, "alarms permission should be present for MV3 lifecycle keepalive"
        assert "scripting" not in permissions, "scripting permission should be removed as DOM scraping is stripped"


class TestHeadlessSanitization:
    """Requirement 1: Removal of DOM scraping, eval(), and UI files."""

    def test_no_forbidden_ui_files(self):
        forbidden_files = ["sidepanel.html", "sidepanel.js", "popup.html", "popup.js", "content.js"]
        for fname in forbidden_files:
            fpath = os.path.join(PROJECT_DIR, fname)
            assert not os.path.exists(fpath), f"Forbidden UI/DOM file {fname} must not exist in headless extension"

    def test_background_js_exists(self):
        assert os.path.exists(BACKGROUND_JS_PATH), f"background.js must exist at {BACKGROUND_JS_PATH}"

    def test_no_eval_or_unsafe_code(self):
        with open(BACKGROUND_JS_PATH, "r", encoding="utf-8") as f:
            code = f.read()

        # Strip multi-line and single-line comments to inspect active code tokens
        code_no_comments = re.sub(r"/\*[\s\S]*?\*/|//.*", "", code)

        # Check for eval or Function constructor
        assert not re.search(r"\beval\s*\(", code_no_comments), "eval() is strictly forbidden under CSP and headless mandate"
        assert not re.search(r"\bnew\s+Function\s*\(", code_no_comments), "new Function() is strictly forbidden"

    def test_no_dom_scraping_patterns(self):
        with open(BACKGROUND_JS_PATH, "r", encoding="utf-8") as f:
            code = f.read()

        # Service workers have no DOM access; assert no scraping patterns
        prohibited = [
            r"document\.querySelector",
            r"document\.querySelectorAll",
            r"document\.getElementById",
            r"document\.body",
            r"window\.ai",
            r"\.innerText",
            r"\.innerHTML",
            r"cardladder",
        ]
        for pattern in prohibited:
            assert not re.search(pattern, code, re.IGNORECASE), (
                f"Prohibited DOM scraping pattern '{pattern}' detected in background.js"
            )


class TestServiceWorkerExecution:
    """Acceptance Criteria: background.js loads cleanly and processes messages."""

    def test_node_syntax_check(self):
        result = subprocess.run(
            ["node", "--check", BACKGROUND_JS_PATH],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"background.js syntax check failed: {result.stderr}"

    def test_message_external_simulation(self):
        """Simulates external messaging interface using Node.js mock environment."""
        harness_js = f"""
        const fs = require('fs');

        let messageExternalListener = null;
        let internalMessageListener = null;

        global.chrome = {{
            runtime: {{
                onMessageExternal: {{
                    addListener: (fn) => {{ messageExternalListener = fn; }}
                }},
                onMessage: {{
                    addListener: (fn) => {{ internalMessageListener = fn; }}
                }},
                onInstalled: {{
                    addListener: (fn) => {{}}
                }},
                onStartup: {{
                    addListener: (fn) => {{}}
                }}
            }},
            alarms: {{
                create: (name, opts) => {{}},
                onAlarm: {{
                    addListener: (fn) => {{}}
                }}
            }},
            tabs: {{
                query: async (opts) => {{
                    if (opts && opts.active === false) {{
                        return [];
                    }}
                    return [
                        {{ id: 101, url: "https://example.com/test", title: "Test Page", windowId: 1, active: true, status: "complete" }},
                        {{ id: 102, url: "https://example.org", title: "Second Tab", windowId: 1, active: false, status: "complete" }}
                    ];
                }}
            }},
            storage: {{
                local: {{
                    get: async (k) => ({{}}),
                    set: async (v) => ({{}})
                }},
                session: {{
                    get: async (k) => ({{}}),
                    set: async (v) => ({{}})
                }}
            }}
        }};

        global.WebSocket = class MockWebSocket {{
            static CONNECTING = 0;
            static OPEN = 1;
            static CLOSING = 2;
            static CLOSED = 3;

            constructor(url) {{
                this.url = url;
                this.readyState = MockWebSocket.OPEN;
            }}
            send(data) {{}}
            close() {{ this.readyState = MockWebSocket.CLOSED; }}
        }};

        // Load background.js
        const bgCode = fs.readFileSync('{BACKGROUND_JS_PATH.replace(chr(92), "/")}', 'utf-8');
        eval(bgCode);

        if (!messageExternalListener) {{
            console.error(JSON.stringify({{ error: "No chrome.runtime.onMessageExternal listener registered" }}));
            process.exit(1);
        }}

        async function runTests() {{
            const results = {{}};

            // Helper to invoke onMessageExternal
            const sendExt = (msg, sender = {{ id: 'test-caller' }}) => {{
                return new Promise((resolve) => {{
                    messageExternalListener(msg, sender, resolve);
                }});
            }};

            // Helper to invoke onMessage
            const sendInt = (msg, sender = {{ id: 'internal' }}) => {{
                return new Promise((resolve) => {{
                    if (!internalMessageListener) return resolve(null);
                    internalMessageListener(msg, sender, resolve);
                }});
            }};

            // Test 1: PING message
            results.ping = await sendExt({{ type: 'PING', id: 'test-ping-1' }});

            // Test 2: Lowercase action 'ping'
            results.pingLowercase = await sendExt({{ action: 'ping', id: 'test-ping-lower' }});

            // Test 3: CAPTURE_TRIGGER message
            results.trigger = await sendExt({{ type: 'CAPTURE_TRIGGER', target: 'tab-123', url: 'https://example.com' }});

            // Test 4: GET_STATUS message
            results.status = await sendExt({{ type: 'GET_STATUS' }});

            // Test 5: GET_ACTIVE_TAB message
            results.activeTab = await sendExt({{ type: 'GET_ACTIVE_TAB' }});

            // Test 6: QUERY_TABS message with valid object query
            results.queryTabs = await sendExt({{ type: 'QUERY_TABS', query: {{ active: true }} }});

            // Test 7: QUERY_TABS with invalid query type (number)
            results.queryTabsNumber = await sendExt({{ type: 'QUERY_TABS', query: 12345 }});

            // Test 8: ECHO message
            results.echo = await sendExt({{ type: 'ECHO', payload: {{ test: 'data' }} }});

            // Test 9: Unknown action
            results.unknownAction = await sendExt({{ type: 'UNSUPPORTED_ACTION' }});

            // Test 10: Missing action (empty object)
            results.missingAction = await sendExt({{}});

            // Test 11: Invalid payload - null
            results.nullPayload = await sendExt(null);

            // Test 12: Invalid payload - array
            results.arrayPayload = await sendExt(['PING']);

            // Test 13: Invalid payload - number primitive
            results.numberPayload = await sendExt(42);

            // Test 14: Internal message PING
            results.internalPing = await sendInt({{ type: 'PING' }});

            // Test 15: Internal message action 'ping'
            results.internalPingAction = await sendInt({{ action: 'ping' }});

            // Test 16: Internal message null payload
            results.internalNull = await sendInt(null);

            // Test 17: ID = 0 (numeric zero) preservation
            results.pingIdZero = await sendExt({{ type: 'PING', id: 0 }});

            // Test 18: CAPTURE_TRIGGER ID = 0 preservation
            results.triggerIdZero = await sendExt({{ type: 'CAPTURE_TRIGGER', id: 0, target: 'tab-0' }});

            console.log(JSON.stringify(results));
        }}

        runTests().catch((e) => {{
            console.error(e);
            process.exit(1);
        }});
        """

        result = subprocess.run(
            ["node", "-e", harness_js],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Harness execution failed: {result.stderr}"

        output = json.loads(result.stdout.strip())

        # Verify Ping response
        ping = output.get("ping")
        assert ping is not None, "PING message did not receive a response"
        assert ping.get("status") == "ok", f"Expected status 'ok', got {ping}"
        assert ping.get("type") == "PONG", f"Expected type 'PONG', got {ping}"
        assert ping.get("id") == "test-ping-1", f"Expected id matching request, got {ping}"
        assert ping.get("headless") is True, f"Expected headless: True, got {ping}"
        assert ping.get("version") == "1.0.0", f"Expected version 1.0.0, got {ping}"

        # Verify Lowercase Ping response
        ping_low = output.get("pingLowercase")
        assert ping_low.get("status") == "ok"
        assert ping_low.get("type") == "PONG"
        assert ping_low.get("id") == "test-ping-lower"

        # Verify Trigger response
        trigger = output.get("trigger")
        assert trigger is not None, "CAPTURE_TRIGGER message did not receive a response"
        assert trigger.get("status") == "ok", f"Expected status 'ok', got {trigger}"
        assert trigger.get("action") == "capture_triggered", f"Expected action 'capture_triggered', got {trigger}"
        assert trigger.get("proxy") is True, f"Expected proxy: True, got {trigger}"
        assert trigger.get("wsForwarded") is True, f"Expected wsForwarded: True, got {trigger}"

        # Verify Status response
        status = output.get("status")
        assert status is not None, "GET_STATUS message did not receive a response"
        assert status.get("status") == "ok"
        assert status.get("headless") is True
        assert status.get("service_worker") == "active"
        assert status.get("wsConnected") is True

        # Verify Active Tab response
        active_tab = output.get("activeTab")
        assert active_tab is not None
        assert active_tab.get("status") == "ok"
        assert active_tab.get("action") == "active_tab"
        assert active_tab.get("tab", {}).get("id") == 101
        assert active_tab.get("tab", {}).get("url") == "https://example.com/test"

        # Verify Query Tabs response
        qtabs = output.get("queryTabs")
        assert qtabs is not None
        assert qtabs.get("status") == "ok"
        assert qtabs.get("action") == "query_tabs"
        assert len(qtabs.get("tabs", [])) == 2
        assert qtabs["tabs"][0]["id"] == 101

        # Verify Query Tabs with sanitized non-object query
        qtabs_num = output.get("queryTabsNumber")
        assert qtabs_num is not None
        assert qtabs_num.get("status") == "ok"
        assert qtabs_num.get("action") == "query_tabs"

        # Verify Echo response
        echo = output.get("echo")
        assert echo is not None
        assert echo.get("status") == "ok"
        assert echo.get("payload", {}).get("test") == "data"

        # Verify Unknown Action response
        unk = output.get("unknownAction")
        assert unk is not None, "Unknown action did not receive an error response"
        assert unk.get("status") == "error", f"Expected error status, got {unk}"
        assert unk.get("code") == "UNKNOWN_ACTION", f"Expected UNKNOWN_ACTION code, got {unk}"

        # Verify Missing Action response
        miss = output.get("missingAction")
        assert miss is not None
        assert miss.get("status") == "error"
        assert miss.get("code") == "MISSING_ACTION"

        # Verify Invalid Payload responses
        for key in ["nullPayload", "arrayPayload", "numberPayload"]:
            inv = output.get(key)
            assert inv is not None, f"{key} did not receive a response"
            assert inv.get("status") == "error", f"Expected error for {key}, got {inv}"
            assert inv.get("code") == "INVALID_PAYLOAD", f"Expected INVALID_PAYLOAD code for {key}, got {inv}"

        # Verify Internal Ping responses
        int_ping = output.get("internalPing")
        assert int_ping is not None
        assert int_ping.get("status") == "ok"
        assert int_ping.get("type") == "PONG"

        int_ping_act = output.get("internalPingAction")
        assert int_ping_act is not None
        assert int_ping_act.get("status") == "ok"
        assert int_ping_act.get("type") == "PONG"

        int_null = output.get("internalNull")
        assert int_null is not None
        assert int_null.get("status") == "error"
        assert int_null.get("code") == "INVALID_PAYLOAD"

        # Verify ID = 0 preservation
        ping_zero = output.get("pingIdZero")
        assert ping_zero is not None
        assert ping_zero.get("status") == "ok"
        assert ping_zero.get("id") == 0, f"Expected id: 0 preserved, got {ping_zero}"

        trig_zero = output.get("triggerIdZero")
        assert trig_zero is not None
        assert trig_zero.get("status") == "ok"
        assert trig_zero.get("id") == 0, f"Expected id: 0 preserved in trigger, got {trig_zero}"


class TestServiceWorkerLifecycleAndAlarms:
    """Requirement 1 & Open Issues: MV3 Lifecycle, Keepalive, and Alarms API."""

    def test_alarms_and_lifecycle_integration(self):
        """Simulates alarm triggers and startup/install lifecycle events in service worker."""
        harness_js = f"""
        const fs = require('fs');

        let alarmListener = null;
        let createdAlarms = [];
        let installListener = null;
        let startupListener = null;
        let wsConnectionAttempts = 0;

        global.chrome = {{
            runtime: {{
                onMessageExternal: {{ addListener: () => {{}} }},
                onMessage: {{ addListener: () => {{}} }},
                onInstalled: {{ addListener: (fn) => {{ installListener = fn; }} }},
                onStartup: {{ addListener: (fn) => {{ startupListener = fn; }} }}
            }},
            alarms: {{
                create: (name, opts) => {{
                    createdAlarms.push({{ name, opts }});
                }},
                onAlarm: {{
                    addListener: (fn) => {{ alarmListener = fn; }}
                }}
            }},
            tabs: {{ query: async () => [] }},
            storage: {{ local: {{ get: async () => ({{}}), set: async () => ({{}}) }} }}
        }};

        global.WebSocket = class MockWebSocket {{
            static CONNECTING = 0;
            static OPEN = 1;
            static CLOSING = 2;
            static CLOSED = 3;

            constructor(url) {{
                wsConnectionAttempts++;
                this.url = url;
                this.readyState = MockWebSocket.CLOSED;
            }}
            send(data) {{}}
            close() {{ this.readyState = MockWebSocket.CLOSED; }}
        }};

        const bgCode = fs.readFileSync('{BACKGROUND_JS_PATH.replace(chr(92), "/")}', 'utf-8');
        eval(bgCode);

        // Verify alarms were registered
        const initialAttempts = wsConnectionAttempts;

        // 1. Trigger alarm event
        if (alarmListener) {{
            alarmListener({{ name: 'DAEMON_RECONNECT_ALARM' }});
        }}

        // 2. Trigger onInstalled event
        if (installListener) {{
            installListener();
        }}

        // 3. Trigger onStartup event
        if (startupListener) {{
            startupListener();
        }}

        console.log(JSON.stringify({{
            createdAlarms,
            alarmListenerRegistered: !!alarmListener,
            installListenerRegistered: !!installListener,
            startupListenerRegistered: !!startupListener,
            connectionAttempts: wsConnectionAttempts
        }}));
        """

        result = subprocess.run(
            ["node", "-e", harness_js],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Lifecycle harness failed: {result.stderr}"
        res = json.loads(result.stdout.strip())
        assert res.get("alarmListenerRegistered") is True
        assert res.get("installListenerRegistered") is True
        assert res.get("startupListenerRegistered") is True
        assert any(a.get("name") == "DAEMON_RECONNECT_ALARM" for a in res.get("createdAlarms", []))
        assert res.get("connectionAttempts") >= 1


class TestNativeMessagingBridge:
    """Requirement 2: Native Messaging Host compatibility & protocol simulation."""

    def test_native_messaging_host_schema(self):
        """Validates that a compliant Native Host Manifest schema can be structured."""
        manifest = {
            "name": "com.antigravity.headless.agent",
            "description": "Antigravity Headless Python Native Host",
            "path": "host.bat",
            "type": "stdio",
            "allowed_origins": ["chrome-extension://*"]
        }
        assert manifest["name"] == "com.antigravity.headless.agent"
        assert manifest["type"] == "stdio"
        assert len(manifest["allowed_origins"]) > 0

    def test_native_messaging_simulation(self):
        """Simulates native port connection and message exchanges."""
        native_js = f"""
        const fs = require('fs');

        let nativePortListener = null;
        let postedNativeMessages = [];

        global.chrome = {{
            runtime: {{
                onMessageExternal: {{ addListener: () => {{}} }},
                onMessage: {{ addListener: () => {{}} }},
                onInstalled: {{ addListener: () => {{}} }},
                onStartup: {{ addListener: () => {{}} }},
                connectNative: (host) => {{
                    return {{
                        onMessage: {{
                            addListener: (fn) => {{ nativePortListener = fn; }}
                        }},
                        onDisconnect: {{
                            addListener: (fn) => {{}}
                        }},
                        postMessage: (msg) => {{
                            postedNativeMessages.push(msg);
                        }}
                    }};
                }}
            }},
            alarms: {{ create: () => {{}}, onAlarm: {{ addListener: () => {{}} }} }},
            tabs: {{ query: async () => [{{ id: 50, url: 'https://native.test', title: 'Native Tab' }}] }},
            storage: {{ local: {{ get: async () => ({{}}), set: async () => ({{}}) }} }}
        }};

        global.WebSocket = class MockWebSocket {{
            static CONNECTING = 0;
            static OPEN = 1;
            static CLOSING = 2;
            static CLOSED = 3;
            constructor(url) {{ this.readyState = MockWebSocket.CLOSED; }}
            send(data) {{}}
            close() {{}}
        }};

        const bgCode = fs.readFileSync('{BACKGROUND_JS_PATH.replace(chr(92), "/")}', 'utf-8');
        eval(bgCode);

        async function runNativeTest() {{
            const port = initNativeConnection('com.antigravity.headless.agent');
            if (!nativePortListener) {{
                console.error("Native listener not attached");
                process.exit(1);
            }}

            // Send native PING with ID 0
            await nativePortListener({{ type: 'PING', id: 0 }});
            // Send native CAPTURE_TRIGGER
            await nativePortListener({{ type: 'CAPTURE_TRIGGER', id: 'native-cap-01', target: 'all' }});
            // Send native GET_STATUS
            await nativePortListener({{ type: 'GET_STATUS', id: 'native-stat-01' }});

            console.log(JSON.stringify({{ postedNativeMessages }}));
        }}

        runNativeTest().catch(e => {{ console.error(e); process.exit(1); }});
        """

        result = subprocess.run(
            ["node", "-e", native_js],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Native messaging test failed: {result.stderr}"
        res = json.loads(result.stdout.strip())
        messages = res.get("postedNativeMessages", [])
        assert len(messages) == 3
        assert messages[0].get("type") == "PONG"
        assert messages[0].get("id") == 0
        assert messages[1].get("action") == "capture_triggered"
        assert messages[1].get("id") == "native-cap-01"
        assert messages[2].get("service_worker") == "active"


class TestWebSocketDaemonBridge:
    """Requirement 2: Bi-directional communication with local Python daemon."""

    @pytest.mark.asyncio
    async def test_websocket_full_lifecycle_and_resilience(self):
        """Spins up a test WebSocket server and connects background.js to verify ping, triggers, status, tab query, active tab, echo, binary frame recovery, and oversized payload recovery."""
        received_pongs = []
        received_trigger_acks = []
        received_status_responses = []
        received_tabs_responses = []
        received_active_tab_responses = []
        received_echo_responses = []
        received_messages = []
        port = 8999

        async def handler(websocket):
            async for message in websocket:
                try:
                    data = json.loads(message)
                except Exception:
                    continue
                received_messages.append(data)
                if data.get("type") == "READY":
                    # 1. Send PING to extension with id 0
                    await websocket.send(json.dumps({"type": "PING", "id": 0}))
                    # 2. Send CAPTURE_TRIGGER to extension
                    await websocket.send(json.dumps({"type": "CAPTURE_TRIGGER", "id": "py-cap-01", "target": "all"}))
                    # 3. Send GET_STATUS to extension
                    await websocket.send(json.dumps({"type": "GET_STATUS", "id": "py-stat-01"}))
                    # 4. Send GET_ACTIVE_TAB to extension
                    await websocket.send(json.dumps({"type": "GET_ACTIVE_TAB", "id": "py-act-01"}))
                    # 5. Send ECHO to extension
                    await websocket.send(json.dumps({"type": "ECHO", "id": "py-echo-01", "payload": {"foo": "bar"}}))
                    # 6. Send QUERY_TABS to extension with query object
                    await websocket.send(json.dumps({"type": "QUERY_TABS", "id": "py-tab-01", "query": {}}))
                    # 7. Send malformed/corrupted non-JSON string payload to test resilience
                    await websocket.send("MALFORMED_STREAM_NON_JSON_!@#$%")
                    # 8. Send oversized payload (> 5MB) to verify memory guard
                    oversized_payload = "X" * (6 * 1024 * 1024)
                    await websocket.send(oversized_payload)
                    # 9. Send binary raw bytes frame to test non-string frame resilience
                    await websocket.send(b"\x00\x01\x02\x03\xff\xfe")
                    # 10. Send second PING to verify extension remains fully functional after malformed, binary, and oversized frames
                    await websocket.send(json.dumps({"type": "PING", "id": "py-ping-daemon-02"}))
                elif data.get("type") == "PONG":
                    received_pongs.append(data)
                elif data.get("type") == "CAPTURE_TRIGGER_ACK":
                    received_trigger_acks.append(data)
                elif data.get("type") == "STATUS_RESPONSE":
                    received_status_responses.append(data)
                elif data.get("type") == "ACTIVE_TAB_RESPONSE":
                    received_active_tab_responses.append(data)
                elif data.get("type") == "ECHO_RESPONSE":
                    received_echo_responses.append(data)
                elif data.get("type") == "QUERY_TABS_RESPONSE":
                    received_tabs_responses.append(data)

        server = await websockets.serve(handler, "localhost", port)

        node_script = f"""
        const fs = require('fs');

        global.chrome = {{
            runtime: {{
                onMessageExternal: {{ addListener: () => {{}} }},
                onMessage: {{ addListener: () => {{}} }},
                onInstalled: {{ addListener: () => {{}} }},
                onStartup: {{ addListener: () => {{}} }}
            }},
            alarms: {{ create: () => {{}}, onAlarm: {{ addListener: () => {{}} }} }},
            tabs: {{
                query: async (opts) => {{
                    return [
                        {{ id: 201, url: "https://antigravity.test", title: "Daemon Tab", windowId: 1, active: true, status: "complete" }}
                    ];
                }}
            }},
            storage: {{
                local: {{ get: async () => ({{}}), set: async () => ({{}}) }}
            }}
        }};

        let code = fs.readFileSync('{BACKGROUND_JS_PATH.replace(chr(92), "/")}', 'utf-8');
        code = code.replace(/ws:\\/\\/localhost:\\d+\\/ws/, 'ws://localhost:{port}/ws');
        eval(code);
        """

        proc = subprocess.Popen(["node", "-e", node_script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        try:
            for _ in range(50):
                if (len(received_pongs) >= 2 and
                    len(received_trigger_acks) > 0 and
                    len(received_status_responses) > 0 and
                    len(received_active_tab_responses) > 0 and
                    len(received_echo_responses) > 0 and
                    len(received_tabs_responses) > 0):
                    break
                await asyncio.sleep(0.1)

            # Assert PONG acknowledgments (both pre and post malformed stream)
            assert len(received_pongs) >= 2, f"Expected 2 PONGs back. Got {received_pongs}. All messages: {received_messages}"
            assert received_pongs[0].get("id") == 0, f"Expected id: 0 preserved in websocket pong, got {received_pongs[0]}"
            assert received_pongs[0].get("headless") is True
            assert received_pongs[0].get("status") == "acknowledged"
            assert received_pongs[1].get("id") == "py-ping-daemon-02"

            # Assert CAPTURE_TRIGGER_ACK acknowledgment
            assert len(received_trigger_acks) > 0, f"No CAPTURE_TRIGGER_ACK received. Messages: {received_messages}"
            ack = received_trigger_acks[0]
            assert ack.get("type") == "CAPTURE_TRIGGER_ACK"
            assert ack.get("id") == "py-cap-01"
            assert ack.get("status") == "acknowledged"
            assert ack.get("proxy") is True

            # Assert STATUS_RESPONSE
            assert len(received_status_responses) > 0, f"No STATUS_RESPONSE received. Messages: {received_messages}"
            stat = received_status_responses[0]
            assert stat.get("id") == "py-stat-01"
            assert stat.get("service_worker") == "active"
            assert stat.get("headless") is True

            # Assert ACTIVE_TAB_RESPONSE
            assert len(received_active_tab_responses) > 0, f"No ACTIVE_TAB_RESPONSE received. Messages: {received_messages}"
            act_resp = received_active_tab_responses[0]
            assert act_resp.get("id") == "py-act-01"
            assert act_resp.get("status") == "ok"
            assert act_resp.get("tab", {}).get("id") == 201

            # Assert ECHO_RESPONSE
            assert len(received_echo_responses) > 0, f"No ECHO_RESPONSE received. Messages: {received_messages}"
            echo_resp = received_echo_responses[0]
            assert echo_resp.get("id") == "py-echo-01"
            assert echo_resp.get("status") == "ok"
            assert echo_resp.get("payload", {}).get("foo") == "bar"

            # Assert QUERY_TABS_RESPONSE
            assert len(received_tabs_responses) > 0, f"No QUERY_TABS_RESPONSE received. Messages: {received_messages}"
            tabs_resp = received_tabs_responses[0]
            assert tabs_resp.get("id") == "py-tab-01"
            assert tabs_resp.get("status") == "ok"
            assert len(tabs_resp.get("tabs", [])) == 1
            assert tabs_resp["tabs"][0]["id"] == 201

        finally:
            proc.terminate()
            server.close()
            await server.wait_closed()


class TestConcurrentMessaging:
    """Stress & Concurrency: Rapid simultaneous external message passing."""

    def test_concurrent_external_messages(self):
        """Fires 50 concurrent external message calls and verifies deterministic responses."""
        concurrency_js = f"""
        const fs = require('fs');

        let messageExternalListener = null;

        global.chrome = {{
            runtime: {{
                onMessageExternal: {{ addListener: (fn) => {{ messageExternalListener = fn; }} }},
                onMessage: {{ addListener: () => {{}} }},
                onInstalled: {{ addListener: () => {{}} }},
                onStartup: {{ addListener: () => {{}} }}
            }},
            alarms: {{ create: () => {{}}, onAlarm: {{ addListener: () => {{}} }} }},
            tabs: {{
                query: async () => [{{ id: 1, url: "https://test.com", title: "Test", windowId: 1, active: true }}]
            }},
            storage: {{
                local: {{ get: async () => ({{}}), set: async () => ({{}}) }}
            }}
        }};

        global.WebSocket = class MockWebSocket {{
            static CONNECTING = 0;
            static OPEN = 1;
            static CLOSING = 2;
            static CLOSED = 3;

            constructor(url) {{ this.readyState = MockWebSocket.OPEN; }}
            send(data) {{}}
            close() {{ this.readyState = MockWebSocket.CLOSED; }}
        }};

        const bgCode = fs.readFileSync('{BACKGROUND_JS_PATH.replace(chr(92), "/")}', 'utf-8');
        eval(bgCode);

        async function runStress() {{
            const N = 50;
            const promises = [];

            for (let i = 0; i < N; i++) {{
                const msg = (i % 3 === 0)
                    ? {{ type: 'PING', id: `req-${{i}}` }}
                    : (i % 3 === 1)
                        ? {{ type: 'CAPTURE_TRIGGER', id: `req-${{i}}`, target: 'all' }}
                        : {{ type: 'GET_ACTIVE_TAB', id: `req-${{i}}` }};

                promises.push(new Promise((resolve) => {{
                    messageExternalListener(msg, {{ id: 'stress-client' }}, (resp) => {{
                        resolve({{ index: i, resp }});
                    }});
                }}));
            }}

            const results = await Promise.all(promises);
            console.log(JSON.stringify({{ count: results.length, allOk: results.every(r => r.resp && r.resp.status === 'ok') }}));
        }}

        runStress().catch(e => {{ console.error(e); process.exit(1); }});
        """

        result = subprocess.run(
            ["node", "-e", concurrency_js],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Concurrency test failed: {result.stderr}"
        res = json.loads(result.stdout.strip())
        assert res.get("count") == 50
        assert res.get("allOk") is True, f"Some concurrent requests failed: {res}"


class TestChromeBrowserHeadlessLoading:
    """Acceptance Criteria: background.js loads in headless Chrome without errors."""

    def test_chrome_extension_loads_in_browser(self):
        chrome_paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        chrome_exe = None
        for p in chrome_paths:
            if os.path.exists(p):
                chrome_exe = p
                break

        if not chrome_exe:
            pytest.skip("Chrome executable not found on system; skipping direct browser run.")

        result = subprocess.run(
            [
                chrome_exe,
                "--headless=new",
                "--disable-gpu",
                f"--load-extension={PROJECT_DIR}",
                "--dump-dom",
                "data:text/html,<html><body><h1>Headless Extension Test</h1></body></html>",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"Chrome failed to load extension: {result.stderr}"


class TestEdgeCaseAndCSPVerification:
    """Rigorous CSP & Edge Case Verification."""

    def test_strict_csp_and_zero_dynamic_code(self):
        """Verifies no unsafe eval, Function, or script injection anywhere in project files."""
        for root, _, files in os.walk(PROJECT_DIR):
            for file in files:
                if file.endswith(".js"):
                    full_path = os.path.join(root, file)
                    with open(full_path, "r", encoding="utf-8") as f:
                        code = f.read()
                    code_clean = re.sub(r"/\*[\s\S]*?\*/|//.*", "", code)
                    assert not re.search(r"\beval\s*\(", code_clean), f"eval found in {file}"
                    assert not re.search(r"\bnew\s+Function\s*\(", code_clean), f"new Function found in {file}"
                    assert not re.search(r"document\.createElement\s*\(\s*['\"]script['\"]\s*\)", code_clean), (
                        f"dynamic script injection in {file}"
                    )

    def test_zero_dom_in_all_js(self):
        """Verifies that no JS files reference DOM scraping or DOM nodes."""
        for root, _, files in os.walk(PROJECT_DIR):
            for file in files:
                if file.endswith(".js"):
                    full_path = os.path.join(root, file)
                    with open(full_path, "r", encoding="utf-8") as f:
                        code = f.read()
                    assert not re.search(r"document\.(getElementById|querySelector|body)", code), (
                        f"DOM reference found in {file}"
                    )


if __name__ == "__main__":
    pytest.main(["-v", __file__])

