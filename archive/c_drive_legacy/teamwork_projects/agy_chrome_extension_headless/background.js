/**
 * Antigravity Headless Background Service Worker (Manifest V3)
 * Pure message passer for omnichannel workflows.
 * No DOM scraping, no UI, zero dynamic code evaluation.
 */

const EXTENSION_VERSION = "1.0.0";
const DEFAULT_DAEMON_URL = "ws://localhost:8002/ws";
const DEFAULT_NATIVE_HOST = "com.antigravity.headless.agent";
const RECONNECT_ALARM_NAME = "DAEMON_RECONNECT_ALARM";
const HEALTH_CHECK_ALARM_NAME = "HEALTH_CHECK_ALARM";

let wsClient = null;
let reconnectTimer = null;
let nativePort = null;

/**
 * Check if a WebSocket instance is currently in OPEN state.
 */
function isWebSocketOpen(ws) {
  if (!ws) return false;
  const openState = (typeof WebSocket !== "undefined" && WebSocket.OPEN !== undefined) ? WebSocket.OPEN : 1;
  return ws.readyState === openState;
}

/**
 * Check if a WebSocket instance is currently in CONNECTING state.
 */
function isWebSocketConnecting(ws) {
  if (!ws) return false;
  const connectingState = (typeof WebSocket !== "undefined" && WebSocket.CONNECTING !== undefined) ? WebSocket.CONNECTING : 0;
  return ws.readyState === connectingState;
}

/**
 * Safely send a JSON payload across a WebSocket without throwing on state transitions.
 */
function safeWebSocketSend(ws, payload) {
  if (!isWebSocketOpen(ws)) return false;
  try {
    const dataStr = typeof payload === "string" ? payload : JSON.stringify(payload);
    ws.send(dataStr);
    return true;
  } catch (err) {
    return false;
  }
}

/**
 * Sanitize query options for tab querying to prevent type mismatch errors.
 */
function sanitizeQueryOptions(query) {
  if (query && typeof query === "object" && !Array.isArray(query)) {
    return query;
  }
  return {};
}

/**
 * Unified message processor across external, internal, WebSocket, and native channels.
 */
async function processMessage(message, senderSource = "external") {
  if (!message || typeof message !== "object" || Array.isArray(message)) {
    return {
      status: "error",
      code: "INVALID_PAYLOAD",
      message: "Payload must be a non-null, non-array object",
    };
  }

  const rawAction = message.type || message.action;
  if (!rawAction || typeof rawAction !== "string") {
    return {
      status: "error",
      code: "MISSING_ACTION",
      message: "Payload must specify a string 'type' or 'action'",
    };
  }

  const messageId = (message.id !== undefined) ? message.id : null;
  const action = rawAction.toUpperCase();

  switch (action) {
    case "PING":
      return {
        status: "ok",
        type: "PONG",
        version: EXTENSION_VERSION,
        id: messageId,
        headless: true,
        timestamp: Date.now(),
      };

    case "CAPTURE_TRIGGER": {
      // Proxy capture trigger without executing DOM scraping.
      // External Python agent handles extraction via Chrome DevTools MCP Accessibility Tree.
      let forwarded = false;
      if (isWebSocketOpen(wsClient)) {
        forwarded = safeWebSocketSend(wsClient, {
          type: "CAPTURE_TRIGGER_FORWARD",
          sender: senderSource,
          payload: message,
          timestamp: Date.now(),
        });
      } else if (!isWebSocketConnecting(wsClient)) {
        // Eagerly restore daemon connection if disconnected
        initDaemonConnection();
      }

      return {
        status: "ok",
        action: "capture_triggered",
        proxy: true,
        wsForwarded: forwarded,
        target: message.target || null,
        url: message.url || null,
        id: messageId,
        timestamp: Date.now(),
      };
    }

    case "GET_STATUS":
      return {
        status: "ok",
        service_worker: "active",
        headless: true,
        version: EXTENSION_VERSION,
        wsConnected: isWebSocketOpen(wsClient),
        id: messageId,
        timestamp: Date.now(),
      };

    case "GET_ACTIVE_TAB": {
      if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query) {
        try {
          const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
          if (tabs && tabs.length > 0) {
            const activeTab = tabs[0];
            return {
              status: "ok",
              action: "active_tab",
              id: messageId,
              tab: {
                id: (activeTab.id !== undefined) ? activeTab.id : null,
                url: activeTab.url || null,
                title: activeTab.title || null,
                windowId: (activeTab.windowId !== undefined) ? activeTab.windowId : null,
                active: Boolean(activeTab.active),
                status: activeTab.status || null,
              },
              timestamp: Date.now(),
            };
          }
          return {
            status: "ok",
            action: "active_tab",
            id: messageId,
            tab: null,
            timestamp: Date.now(),
          };
        } catch (tabErr) {
          return {
            status: "error",
            code: "TABS_QUERY_ERROR",
            message: tabErr.message || String(tabErr),
          };
        }
      }
      return {
        status: "error",
        code: "TABS_UNAVAILABLE",
        message: "chrome.tabs API is not available",
      };
    }

    case "QUERY_TABS": {
      if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query) {
        try {
          const queryOptions = sanitizeQueryOptions(message.query);
          const tabs = await chrome.tabs.query(queryOptions);
          const tabList = (tabs || []).map((t) => ({
            id: (t.id !== undefined) ? t.id : null,
            url: t.url || null,
            title: t.title || null,
            windowId: (t.windowId !== undefined) ? t.windowId : null,
            active: Boolean(t.active),
            status: t.status || null,
          }));
          return {
            status: "ok",
            action: "query_tabs",
            id: messageId,
            tabs: tabList,
            timestamp: Date.now(),
          };
        } catch (tabErr) {
          return {
            status: "error",
            code: "TABS_QUERY_ERROR",
            message: tabErr.message || String(tabErr),
          };
        }
      }
      return {
        status: "error",
        code: "TABS_UNAVAILABLE",
        message: "chrome.tabs API is not available",
      };
    }

    case "ECHO":
      return {
        status: "ok",
        action: "echo",
        id: messageId,
        payload: (message.payload !== undefined) ? message.payload : null,
        timestamp: Date.now(),
      };

    default:
      return {
        status: "error",
        code: "UNKNOWN_ACTION",
        message: `Unsupported action type: ${rawAction}`,
        received: rawAction,
        id: messageId,
      };
  }
}

/**
 * Handle incoming external messages from web pages or external callers.
 */
chrome.runtime.onMessageExternal.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      const senderDesc = (sender && (sender.id || sender.origin || sender.url)) || "external";
      const response = await processMessage(message, senderDesc);
      try {
        sendResponse(response);
      } catch (_) {}
    } catch (err) {
      try {
        sendResponse({
          status: "error",
          code: "INTERNAL_ERROR",
          message: err.message || String(err),
        });
      } catch (_) {}
    }
  })();

  return true; // Keep channel open for async response
});

/**
 * Handle internal extension messages.
 */
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  (async () => {
    try {
      const response = await processMessage(message, "internal");
      try {
        sendResponse(response);
      } catch (_) {}
    } catch (err) {
      try {
        sendResponse({
          status: "error",
          code: "INTERNAL_ERROR",
          message: err.message || String(err),
        });
      } catch (_) {}
    }
  })();

  return true;
});

/**
 * Connect to the local Python daemon over WebSocket.
 */
function initDaemonConnection(customUrl) {
  if (typeof WebSocket === "undefined") {
    return null;
  }

  // Prevent duplicate connections if already open or connecting
  if (isWebSocketOpen(wsClient) || isWebSocketConnecting(wsClient)) {
    return wsClient;
  }

  const targetUrl = customUrl || DEFAULT_DAEMON_URL;

  try {
    wsClient = new WebSocket(targetUrl);

    wsClient.onopen = () => {
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      // Announce readiness to Python daemon
      safeWebSocketSend(wsClient, {
        type: "READY",
        version: EXTENSION_VERSION,
        headless: true,
        timestamp: Date.now(),
      });
    };

    wsClient.onmessage = async (event) => {
      try {
        // Defensive: ignore null events or non-string frames (e.g. binary ArrayBuffer / Blob)
        if (!event || typeof event.data !== "string") {
          return;
        }

        // Defensive: guard against memory exhaustion from oversized stream payloads (> 5MB)
        if (event.data.length > 5 * 1024 * 1024) {
          return;
        }

        let data = null;
        try {
          data = JSON.parse(event.data);
        } catch (_) {
          return; // Suppress malformed JSON from stream
        }

        if (!data || typeof data !== "object" || Array.isArray(data)) return;

        const rawType = data.type || data.action;
        if (!rawType || typeof rawType !== "string") return;
        const type = rawType.toUpperCase();
        const dataId = (data.id !== undefined) ? data.id : null;

        switch (type) {
          case "PING":
            safeWebSocketSend(wsClient, {
              type: "PONG",
              id: dataId,
              status: "acknowledged",
              headless: true,
              version: EXTENSION_VERSION,
              timestamp: Date.now(),
            });
            break;

          case "CAPTURE_TRIGGER":
            safeWebSocketSend(wsClient, {
              type: "CAPTURE_TRIGGER_ACK",
              id: dataId,
              status: "acknowledged",
              proxy: true,
              timestamp: Date.now(),
            });
            break;

          case "GET_STATUS":
            safeWebSocketSend(wsClient, {
              type: "STATUS_RESPONSE",
              id: dataId,
              status: "ok",
              service_worker: "active",
              headless: true,
              version: EXTENSION_VERSION,
              wsConnected: true,
              timestamp: Date.now(),
            });
            break;

          case "GET_ACTIVE_TAB": {
            if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query) {
              try {
                const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
                const activeTab = (tabs && tabs.length > 0) ? tabs[0] : null;
                safeWebSocketSend(wsClient, {
                  type: "ACTIVE_TAB_RESPONSE",
                  id: dataId,
                  status: "ok",
                  tab: activeTab ? {
                    id: (activeTab.id !== undefined) ? activeTab.id : null,
                    url: activeTab.url || null,
                    title: activeTab.title || null,
                    windowId: (activeTab.windowId !== undefined) ? activeTab.windowId : null,
                    active: Boolean(activeTab.active),
                    status: activeTab.status || null,
                  } : null,
                  timestamp: Date.now(),
                });
              } catch (tabErr) {
                safeWebSocketSend(wsClient, {
                  type: "ACTIVE_TAB_RESPONSE",
                  id: dataId,
                  status: "error",
                  message: tabErr.message || String(tabErr),
                  timestamp: Date.now(),
                });
              }
            }
            break;
          }

          case "QUERY_TABS": {
            if (typeof chrome !== "undefined" && chrome.tabs && chrome.tabs.query) {
              try {
                const queryOptions = sanitizeQueryOptions(data.query);
                const tabs = await chrome.tabs.query(queryOptions);
                const tabList = (tabs || []).map((t) => ({
                  id: (t.id !== undefined) ? t.id : null,
                  url: t.url || null,
                  title: t.title || null,
                  windowId: (t.windowId !== undefined) ? t.windowId : null,
                  active: Boolean(t.active),
                  status: t.status || null,
                }));
                safeWebSocketSend(wsClient, {
                  type: "QUERY_TABS_RESPONSE",
                  id: dataId,
                  status: "ok",
                  tabs: tabList,
                  timestamp: Date.now(),
                });
              } catch (tabErr) {
                safeWebSocketSend(wsClient, {
                  type: "QUERY_TABS_RESPONSE",
                  id: dataId,
                  status: "error",
                  message: tabErr.message || String(tabErr),
                  timestamp: Date.now(),
                });
              }
            }
            break;
          }

          case "ECHO":
            safeWebSocketSend(wsClient, {
              type: "ECHO_RESPONSE",
              id: dataId,
              status: "ok",
              payload: (data.payload !== undefined) ? data.payload : null,
              timestamp: Date.now(),
            });
            break;

          default:
            break;
        }
      } catch (_) {
        // Safe error suppression
      }
    };

    wsClient.onerror = () => {
      // Suppress connection errors when daemon is offline
    };

    wsClient.onclose = () => {
      wsClient = null;
      scheduleReconnect(targetUrl);
    };
  } catch (e) {
    wsClient = null;
    scheduleReconnect(targetUrl);
  }

  return wsClient;
}

/**
 * Schedule reconnect attempt via timer (ephemeral fallback).
 */
function scheduleReconnect(targetUrl) {
  if (!reconnectTimer) {
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null;
      initDaemonConnection(targetUrl);
    }, 5000);
  }
}

/**
 * Optional Native Messaging port connection.
 */
function initNativeConnection(hostName) {
  if (typeof chrome === "undefined" || !chrome.runtime || !chrome.runtime.connectNative) {
    return null;
  }
  if (nativePort) return nativePort;

  try {
    const host = hostName || DEFAULT_NATIVE_HOST;
    nativePort = chrome.runtime.connectNative(host);

    nativePort.onMessage.addListener(async (msg) => {
      const response = await processMessage(msg, "native");
      if (nativePort) {
        try {
          nativePort.postMessage(response);
        } catch (_) {}
      }
    });

    nativePort.onDisconnect.addListener(() => {
      // Consume lastError to suppress Chrome's "Unchecked runtime.lastError" warning
      if (typeof chrome !== "undefined" && chrome.runtime && chrome.runtime.lastError) {
        // Suppress warning when native host is not found or disconnects
      }
      nativePort = null;
    });

    return nativePort;
  } catch (e) {
    nativePort = null;
    return null;
  }
}

/**
 * Initialize Manifest V3 lifecycle events and alarm triggers.
 */
function setupLifecycle() {
  if (typeof chrome === "undefined" || !chrome.runtime) return;

  // 1. Setup Chrome Alarms for keepalive and daemon reconnect
  if (chrome.alarms) {
    try {
      chrome.alarms.create(RECONNECT_ALARM_NAME, {
        periodInMinutes: 1,
      });
    } catch (_) {}

    chrome.alarms.onAlarm.addListener((alarm) => {
      if (alarm.name === RECONNECT_ALARM_NAME || alarm.name === HEALTH_CHECK_ALARM_NAME) {
        if (!isWebSocketOpen(wsClient) && !isWebSocketConnecting(wsClient)) {
          initDaemonConnection();
        }
      }
    });
  }

  // 2. Setup Startup / Installed lifecycle hooks
  if (chrome.runtime.onInstalled) {
    chrome.runtime.onInstalled.addListener(() => {
      initDaemonConnection();
    });
  }

  if (chrome.runtime.onStartup) {
    chrome.runtime.onStartup.addListener(() => {
      initDaemonConnection();
    });
  }
}

// Initialize lifecycle listeners and daemon connection on service worker startup
setupLifecycle();
initDaemonConnection();

