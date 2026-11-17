/* DrRoshan PWA — service worker (no dependencies, vanilla) */
const VERSION = 'hr-pwa-v3';
const CORE = [
  './',
  './index.html',
  './cart.html',
  './checkout.html',
  './payment.html',
  './style.css',
  './shop.css',
  './shop.js',
  './manifest.json',
  './profile.jpg',
  './favicon-32x32.png',
  './pwa-192.png',
  './pwa-512.png'
];
const OFFLINE_URL = './index.html';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(CORE))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  // Page navigations: network first, fall back to cache, then to home (offline).
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((cache) => cache.put(req, copy));
          return res;
        })
        .catch(() =>
          caches.match(req).then((hit) => hit || caches.match(OFFLINE_URL))
        )
    );
    return;
  }

  // Static assets (images, css, js): stale-while-revalidate —
  // serve the cached copy instantly, refresh the cache in the background so
  // CSS/JS updates reach users after at most one reload.
  event.respondWith(
    caches.match(req).then((hit) => {
      const network = fetch(req).then((res) => {
        if (res && res.ok && new URL(req.url).origin === self.location.origin) {
          const copy = res.clone();
          caches.open(VERSION).then((cache) => cache.put(req, copy));
        }
        return res;
      }).catch(() => hit);
      return hit || network;
    })
  );
});
