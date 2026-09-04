import '@testing-library/jest-dom';

if (typeof window !== 'undefined') {
  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  });

  class MockResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  (window as any).ResizeObserver = MockResizeObserver;

  class MockEventSource {
    url: string;
    onmessage: ((event: any) => void) | null = null;
    onerror: ((event: any) => void) | null = null;
    readyState = 1;
    constructor(url: string) {
      this.url = url;
      setTimeout(() => {
        if (this.onmessage) {
          this.onmessage({ data: 'Connected to pipeline stream.' });
        }
      }, 10);
    }
    close() {
      this.readyState = 2;
    }
  }
  (window as any).EventSource = MockEventSource;
}
