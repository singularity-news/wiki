// sw.js

const CACHE =
  "encyclopedia-cache-v1";

const OFFLINE = [
  "/",
  "/encyclopedia.html",
  "/search-index.json",
  "/assets/style.css",
  "/assets/app.js"
];

self.addEventListener("install", event => {

  event.waitUntil(

    caches.open(CACHE)
      .then(cache => cache.addAll(OFFLINE))

  );

});

self.addEventListener("fetch", event => {

  event.respondWith(

    caches.match(event.request)
      .then(response => {

        return response || fetch(event.request);

      })

  );

});
