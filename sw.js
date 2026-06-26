const CACHE_NAME = 'cra-camila-v1';

// Opcional: Recursos a cachear por defecto
const urlsToCache = [
  '/',
  '/index.html',
  '/app.js',
  '/app_icon.png',
  '/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        return cache.addAll(urlsToCache);
      })
  );
});

self.addEventListener('fetch', event => {
  // Estrategia básica: Network first, fallback to cache
  event.respondWith(
    fetch(event.request).catch(() => {
      return caches.match(event.request);
    })
  );
});
