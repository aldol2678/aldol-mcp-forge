const CACHE = "aldol-mobile-pwa-v1";
const FILES = [
  "/mobile/",
  "/mobile/index.html",
  "/mobile/styles.css",
  "/mobile/app.js",
  "/mobile/manifest.webmanifest",
  "/mobile/icon-192.png",
  "/mobile/icon-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(FILES)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/mobile/api/")) return;
  if (!url.pathname.startsWith("/mobile/")) return;
  event.respondWith((async () => {
    try {
      const fresh = await fetch(event.request);
      if (fresh.ok) {
        const cache = await caches.open(CACHE);
        await cache.put(event.request, fresh.clone());
      }
      return fresh;
    } catch (error) {
      const cached = await caches.match(event.request) || await caches.match("/mobile/");
      if (cached) return cached;
      throw error;
    }
  })());
});
