/* ===================================================
   Singularity University Encyclopedia
   sw.js  —  Service Worker (Offline PWA)
   Cache-first for static assets, network-first for
   article HTML so fresh content is always preferred.
   =================================================== */

const CACHE_NAME    = 'su-encyclopedia-v2';
const OFFLINE_PAGE  = '/index.html';

/* Assets that are always cached on install */
const PRECACHE = [
  '/',
  '/index.html',
  '/assets/style.css',
  '/assets/app.js',
  '/search-index.json',
  '/manifest.json'
];

/* ── Install ── */
self.addEventListener('install', event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(PRECACHE))
  );
});

/* ── Activate: clean up old caches ── */
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(k => k !== CACHE_NAME)
          .map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

/* ── Fetch strategy ── */
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  /* Skip non-GET and cross-origin (except GitHub raw assets) */
  if (request.method !== 'GET') return;
  if (
    url.origin !== self.location.origin &&
    !url.hostname.includes('raw.githubusercontent.com')
  ) return;

  /* search-index.json: network first, fallback to cache */
  if (url.pathname.endsWith('search-index.json')) {
    event.respondWith(networkFirst(request));
    return;
  }

  /* HTML article pages: network first, fallback to cache */
  if (
    request.headers.get('Accept')?.includes('text/html') ||
    url.pathname.endsWith('.html')
  ) {
    event.respondWith(networkFirstHTML(request));
    return;
  }

  /* CSS / JS / images: cache first */
  event.respondWith(cacheFirst(request));
});

/* ── Strategies ── */

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline – Ressource nicht verfügbar.', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    return cached || new Response('[]', {
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    });
  }
}

async function networkFirstHTML(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    /* Fallback to index as offline shell */
    return caches.match(OFFLINE_PAGE) || new Response(
      '<h1>Offline</h1><p>Keine Verbindung. Bitte später erneut versuchen.</p>',
      { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
    );
  }
}
