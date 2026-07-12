const CACHE_NAME = 'medquiz-v6';
const ASSETS = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  'https://cdn.jsdelivr.net/npm/d3@7'
];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(ASSETS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
    )).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  // Skip non-http/https requests (like chrome-extension or file schemes)
  if (!e.request.url.startsWith('http://') && !e.request.url.startsWith('https://')) {
    return;
  }

  // Cache-first for app shell, network-first with cache fallback for other assets
  if (e.request.destination === 'image') {
    e.respondWith(
      fetch(e.request).then(res => {
        if (res.status === 200) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return res;
      }).catch(() => caches.match(e.request))
    );
  } else {
    e.respondWith(
      fetch(e.request).then(res => {
        // Cache successful GET responses
        if (e.request.method === 'GET' && (res.status === 200 || res.status === 0)) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(e.request, clone));
        }
        return res;
      }).catch(err => {
        console.log('Fetch failed, trying cache:', err);
        return caches.match(e.request).then(cached => {
          if (cached) return cached;
          // Fallback to index.html for navigation requests
          if (e.request.mode === 'navigate') {
            return caches.match('./index.html') || caches.match('./');
          }
          return new Response('Network error happened', { status: 408, headers: { 'Content-Type': 'text/plain' } });
        });
      })
    );
  }
});
