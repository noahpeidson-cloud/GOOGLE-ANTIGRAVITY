// Allow users to open the side panel by clicking the extension icon
chrome.sidePanel
  .setPanelBehavior({ openPanelOnActionClick: true })
  .catch((error) => console.error(error));

let ws = null;

function connectWebSocket() {
  // Connect to local Python Daemon
  ws = new WebSocket('ws://localhost:8002/ws');

  ws.onopen = () => {
    console.log("Connected to Antigravity Local Daemon.");
  };

  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    // Route backend commands to the active tab's content script
    if (data.type === 'EXECUTE_DOM_ACTION') {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs[0]) {
          chrome.tabs.sendMessage(tabs[0].id, data);
        }
      });
    }
  };

  ws.onclose = () => {
    console.log("Disconnected. Reconnecting in 5s...");
    setTimeout(connectWebSocket, 5000);
  };
}

connectWebSocket();

// Listen for messages from content.js or sidepanel.js and pass to backend
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.target === 'backend' && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(message.payload));
  }
});
