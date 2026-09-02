/**
 * Service Worker for EDM Pipeline Master Mind PWA
 * Cache-First for static assets, Network-First for dynamic API endpoints.
 */

const CACHE_NAME = 'edm-pwa-v1';
const STATIC_ASSETS = [
  '/',
  '/static/index.html',
  '/static/manifest.json',
  '/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png'
];

// Install Event: Pre-cache core shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Pre-caching non-fatal warning:', err);
      });
    }).then(() => {
      return self.skipWaiting();
    })
  );
});

// Activate Event: Clean up stale caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    }).then(() => {
      return self.clients.claim();
    })
  );
});

// Fetch Event: Cache-First for static, Network-First for API
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // Only handle same-origin requests or specific HTTP schemes
  if (request.method !== 'GET') {
    // Non-GET requests (e.g. POST /trigger-pipeline, POST /approve-render) always go to network
    return;
  }

  // Network-First paths: API endpoints, video proxies, health, status, telemetry
  const isApiRequest = (
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/proxies/') ||
    url.pathname === '/trigger-pipeline' ||
    url.pathname === '/approve-render' ||
    url.pathname === '/health' ||
    url.pathname === '/status' ||
    url.pathname === '/logs' ||
    url.pathname === '/cancel'
  );

  if (isApiRequest) {
    // Network-First with Cache fallback
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(request, clone);
            });
          }
          return response;
        })
        .catch(async () => {
          const cached = await caches.match(request);
          if (cached) return cached;
          return new Response(JSON.stringify({ error: 'Network unavailable (offline)' }), {
            status: 503,
            headers: { 'Content-Type': 'application/json' }
          });
        })
    );
    return;
  }

  // Cache-First strategy for static assets (HTML, JS, CSS, PNG, JSON, etc.)
  event.respondWith(
    caches.match(request).then((cachedResponse) => {
      if (cachedResponse) {
        // Return cached and refresh in background
        fetch(request).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            caches.open(CACHE_NAME).then((cache) => cache.put(request, networkResponse));
          }
        }).catch(() => {/* ignore background refresh failure */});
        return cachedResponse;
      }

      // If not in cache, fetch from network and cache
      return fetch(request).then((networkResponse) => {
        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
          return networkResponse;
        }
        const responseToCache = networkResponse.clone();
        caches.open(CACHE_NAME).then((cache) => {
          cache.put(request, responseToCache);
        });
        return networkResponse;
      }).catch(async () => {
        // Fallback for navigation requests (HTML shell)
        if (request.mode === 'navigate') {
          const fallback = await caches.match('/static/index.html') || await caches.match('/');
          if (fallback) return fallback;
        }
        return new Response('Offline: Asset not available in cache', { status: 503, headers: { 'Content-Type': 'text/plain' } });
      });
    })
  );
});
