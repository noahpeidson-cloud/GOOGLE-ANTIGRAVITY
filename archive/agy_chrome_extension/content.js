console.log("Antigravity Content Script Injected.");

// Listen for commands from the background service worker
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === 'EXECUTE_DOM_ACTION') {
    const { action, selector, value } = request;
    const element = document.querySelector(selector);
    
    if (!element) {
      console.warn(Element not found: );
      sendResponse({ status: 'error', message: 'Element not found' });
      return;
    }

    if (action === 'click') {
      element.click();
      sendResponse({ status: 'success', action: 'clicked' });
    } else if (action === 'type') {
      element.value = value;
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
      sendResponse({ status: 'success', action: 'typed' });
    } else if (action === 'scrape') {
      // Execute Edge AI Processing via Chrome Built-in Gemini Nano
      (async () => {
        try {
          const rawData = document.body.innerText;
          let finalPayload = rawData;

          // Feature detect Chrome's Prompt API (window.ai or window.ai.languageModel)
          const aiAPI = window.ai?.languageModel || window.ai;
          
          if (aiAPI) {
            console.log("[EDGE_AI] Initializing local Gemini Nano session...");
            // Use standard summarization prompt logic
            const session = await aiAPI.create();
            console.log("[EDGE_AI] Prompting local model...");
            finalPayload = await session.prompt(`Summarize the following web page content concisely, focusing on key data points:\n\n${rawData.substring(0, 3000)}`);
            session.destroy();
            console.log("[EDGE_AI] Local inference complete.");
          } else {
            console.warn("[EDGE_AI] window.ai not detected. Ensure Chrome flags are enabled. Falling back to raw DOM.");
          }

          chrome.runtime.sendMessage({
            target: 'backend',
            payload: { type: 'DOM_DATA_PROCESSED', url: window.location.href, content: finalPayload }
          });
          sendResponse({ status: 'success', action: 'scraped_and_processed' });
        } catch (err) {
          console.error("[EDGE_AI] Inference Error:", err);
          sendResponse({ status: 'error', message: err.toString() });
        }
      })();
      return true; // Keep the message channel open for the async response
    }
  }
});

// Example: Proactively scrape Card Ladder table if on the domain
if (window.location.hostname.includes('cardladder')) {
  setTimeout(() => {
     const salesData = document.querySelector('table') ? document.querySelector('table').innerText : '';
     if (salesData) {
       chrome.runtime.sendMessage({
         target: 'backend',
         payload: { type: 'CARD_LADDER_DATA', url: window.location.href, content: salesData }
       });
     }
  }, 3000);
}
