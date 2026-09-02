const captureBtn = document.getElementById('captureBtn');
const saveBtn = document.getElementById('saveBtn');
const statusDiv = document.getElementById('status');
const resultArea = document.getElementById('resultArea');

function setStatus(msg, type = '') {
  statusDiv.textContent = msg;
  statusDiv.className = type;
}

captureBtn.addEventListener('click', async () => {
  try {
    captureBtn.disabled = true;
    saveBtn.disabled = true;
    resultArea.value = '';
    
    let sourceText = '';
    
    // 1. Check if we have highlighted text from the context menu
    const { highlightedText } = await chrome.storage.session.get('highlightedText');
    
    if (highlightedText) {
      setStatus('Using highlighted text...');
      sourceText = highlightedText;
    } else {
      setStatus('No highlight found, extracting full page text...');
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) throw new Error('No active tab found.');
      const injection = await chrome.scripting.executeScript({
        target: { tabId: tab.id },
        func: () => document.body.innerText
      });
      sourceText = injection[0].result;
    }

    if (!sourceText || sourceText.trim().length === 0) {
      throw new Error('No text found to process.');
    }

    setStatus('Initializing Chrome Prompt API...');

    if (!('ai' in self) || !('languageModel' in self.ai)) {
      throw new Error('Chrome Prompt API (ai.languageModel) is not available.');
    }
    
    const capabilities = await self.ai.languageModel.capabilities();
    if (capabilities.available === 'no') {
      throw new Error('Language model is not available.');
    }

    setStatus('Extracting Card Ladder Schema (this may take a moment)...');

    const session = await self.ai.languageModel.create({
      systemPrompt: `You are a sports card data extraction assistant. Extract details from the text into strict JSON format with these exact keys:
"Date Purchased", "Quantity", "Player", "Year", "Set", "Variation", "Number", "Category", "Condition", "Slab Serial #", "Investment", "Estimated Value", "Ladder ID", "Query", "Notes", "Tags", "Date Sold", "Sold Price", "Image", "Back Image", "AI Status".
Rules: Quantity is 1. Investment and Estimated Value are 0.00. Ladder ID is blank. AI Status is "CLEARED". Condition is "Raw" or the graded syntax (e.g. "PSA 10"). Category must be a standard sports category. Output ONLY valid JSON.`
    });

    const safeText = sourceText.substring(0, 4000); 
    const response = await session.prompt(`Extract the card details into JSON:\n\n${safeText}`);
    
    let cleanJson = response.trim();
    if (cleanJson.startsWith('```json')) cleanJson = cleanJson.replace(/```json/g, '').replace(/```/g, '').trim();

    JSON.parse(cleanJson); // verify

    resultArea.value = cleanJson;
    setStatus('Capture complete!', 'success');
    saveBtn.disabled = false;
    
    session.destroy();

    // Clear the highlight so it doesn't get reused accidentally
    await chrome.storage.session.remove('highlightedText');

  } catch (err) {
    console.error(err);
    setStatus(`Error: ${err.message}`, 'error');
  } finally {
    captureBtn.disabled = false;
  }
});

saveBtn.addEventListener('click', async () => {
  try {
    const data = JSON.parse(resultArea.value);
    setStatus('Saving to local inbox...', '');
    
    // Send to local Python FastAPI server
    const res = await fetch('http://localhost:8080/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        source_url: await getCurrentUrl(),
        timestamp: new Date().toISOString(),
        extracted_data: data
      })
    });

    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    
    setStatus('Saved successfully!', 'success');
    saveBtn.disabled = true;
    setTimeout(() => { setStatus('Ready', ''); }, 3000);

  } catch (err) {
    console.error(err);
    setStatus(`Failed to save: ${err.message}. Is the local inbox server running?`, 'error');
  }
});

async function getCurrentUrl() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab ? tab.url : 'unknown';
}
