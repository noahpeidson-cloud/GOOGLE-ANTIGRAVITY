const log = document.getElementById('chat-log');
const input = document.getElementById('user-input');
const btn = document.getElementById('send-btn');

function appendMessage(sender, text) {
  const div = document.createElement('div');
  div.className = message ;
  div.innerHTML = <strong>:</strong> ;
  log.appendChild(div);
  log.scrollTop = log.scrollHeight;
}

btn.addEventListener('click', () => {
  const text = input.value.trim();
  if (!text) return;
  
  appendMessage('User', text);
  input.value = '';

  // Get current tab URL to send along with the prompt
  chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
    const url = tabs[0] ? tabs[0].url : 'Unknown';
    
    // Send to background worker (which pipes it to Antigravity WebSocket)
    chrome.runtime.sendMessage({
      target: 'backend',
      payload: {
        type: 'USER_CHAT',
        text: text,
        context_url: url
      }
    });
    
    // Trigger a scrape to send current DOM context instantly
    if (tabs[0]) {
      chrome.tabs.sendMessage(tabs[0].id, { action: 'scrape' });
    }
  });
});

input.addEventListener('keypress', (e) => {
  if (e.key === 'Enter') btn.click();
});
