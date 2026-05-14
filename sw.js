/* Singularity University Encyclopedia | sw.js */
/* Cache-first for assets, network-first for pages and JSON */

var CACHE = 'su-enc-v2';
var OFFLINE = '/index.html';
var PRECACHE = [
  '/',
  '/index.html',
  '/assets/style.css',
  '/assets/app.js',
  '/search-index.json',
  '/manifest.json'
];

self.addEventListener('install', function (e) {
  self.skipWaiting();
  e.waitUntil(
    caches.open(CACHE).then(function (c) { return c.addAll(PRECACHE); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); })
      );
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  var url = new URL(req.url);
  if (req.method !== 'GET') return;
  if (url.origin !== self.location.origin && !url.hostname.includes('raw.githubusercontent.com')) return;

  if (url.pathname.endsWith('search-index.json') || url.pathname.endsWith('.html')) {
    e.respondWith(networkFirst(req));
  } else {
    e.respondWith(cacheFirst(req));
  }
});

function cacheFirst(req) {
  return caches.match(req).then(function (cached) {
    if (cached) return cached;
    return fetch(req).then(function (resp) {
      if (resp.ok) {
        caches.open(CACHE).then(function (c) { c.put(req, resp.clone()); });
      }
      return resp;
    }).catch(function () {
      return new Response('Offline.', { status: 503, headers: { 'Content-Type': 'text/plain' } });
    });
  });
}

function networkFirst(req) {
  return fetch(req).then(function (resp) {
    if (resp.ok) {
      caches.open(CACHE).then(function (c) { c.put(req, resp.clone()); });
    }
    return resp;
  }).catch(function () {
    return caches.match(req).then(function (cached) {
      return cached || caches.match(OFFLINE) || new Response(
        '<h1>Offline</h1>',
        { headers: { 'Content-Type': 'text/html' } }
      );
    });
  });
}
