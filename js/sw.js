const CACHE = "ytremote-v2";
const ASSETS = ["/", "/manifest.webmanifest", "/sw.js", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(ASSETS);
    self.skipWaiting();
  })());
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k)));
    self.clients.claim();
  })());
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.pathname.startsWith("/api/")) return; // always network for actions/status

  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const cached = await cache.match(event.request);
    if (cached) return cached;
    try {
      const res = await fetch(event.request);
      if (event.request.method === "GET" && res && res.status === 200) {
        cache.put(event.request, res.clone());
      }
      return res;
    } catch (e) {
      return (await cache.match("/")) || new Response("Offline", {status: 200});
    }
  })());
});