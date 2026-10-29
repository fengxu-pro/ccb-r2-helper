const CACHE = 'ccb-r1r2-v1';
const ASSETS = [
  './',
  './index.html',
  './data.js',
  './libs/xlsx.full.min.js',
  './manifest.webmanifest',
  './icon-192.png',
  './icon-512.png',
  './version.json'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((ks) =>
      Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  // 网络优先（保证"拉新"和"检查更新"拿到最新），失败回退缓存
  e.respondWith(
    fetch(e.request)
      .then((resp) => {
        const cp = resp.clone();
        caches.open(CACHE).then((c) => c.put(e.request, cp));
        return resp;
      })
      .catch(() => caches.match(e.request).then((r) => r || caches.match('./index.html')))
  );
});
