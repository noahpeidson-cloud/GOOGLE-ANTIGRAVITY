chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: 'capture-card',
    title: 'Capture Highlighted Card',
    contexts: ['selection']
  });
});

chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === 'capture-card') {
    // Save the selected text to session storage so the side panel can read it
    await chrome.storage.session.set({ highlightedText: info.selectionText });
    
    // Open the side panel
    await chrome.sidePanel.open({ windowId: tab.windowId });
  }
});

chrome.action.onClicked.addListener(async (tab) => {
  // Clear any old highlighted text when opened manually
  await chrome.storage.session.remove('highlightedText');
  await chrome.sidePanel.open({ windowId: tab.windowId });
});
