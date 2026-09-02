// injector.js - Executes in the MAIN world, sharing window context with Antigravity UI
(function() {
    const originalFetch = window.fetch;
    
    window.fetch = async function(...args) {
        const url = typeof args[0] === 'string' ? args[0] : args[0]?.url;
        const response = await originalFetch.apply(this, args);
        
        // Target the model fetching endpoint (adjust regex based on exact Antigravity network trace)
        if (url && url.includes('/api/models')) {
            const clonedResponse = response.clone();
            try {
                const data = await clonedResponse.json();
                
                // Construct injected models
                const injectedModels = [];
                
                // Method A: Chrome Native AI (Gemini Nano)
                if (window.LanguageModel) {
                    injectedModels.push({
                        id: "chrome-builtin-gemini-nano",
                        name: "Gemini Nano (Chrome Local)",
                        provider: "window.ai",
                        contextWindow: 4000
                    });
                }
                
                // Method B: LiteLLM / Ollama Proxy
                injectedModels.push({
                    id: "claude-fable-5.0-proxy",
                    name: "Claude Fable 5.0 (LiteLLM)",
                    provider: "local-proxy",
                    endpoint: "http://localhost:11434/v1"
                });

                // Append and return mocked Response object
                data.models = [...(data.models || []), ...injectedModels];
                
                return new Response(JSON.stringify(data), {
                    status: response.status,
                    statusText: response.statusText,
                    headers: response.headers
                });
            } catch (e) {
                console.error("Antigravity Model Injector failed to parse response:", e);
                return response;
            }
        }
        return response;
    };
})();
