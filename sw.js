/* Góndola · service worker: la app abre sin señal.
   - La página se sirve al instante desde el celular y se actualiza en segundo plano cuando hay red
     (el aviso "Hay una versión nueva, recargá" indica cuándo recargar).
   - GitHub (versiones) y Google Apps Script (sincronización) van siempre por la red. */
const SHELL = 'gondola-shell-v1';
const RUNTIME = 'gondola-runtime-v1'; // tipografías, lector de códigos (ZXing) y catálogo SEPA // tipografías y lector de códigos (ZXing)
const PRECACHE = ['./', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => ![SHELL, RUNTIME].includes(k)).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  if (/(^|\.)github\.com$|googleusercontent\.com$|script\.google\.com$|api\.github\.com$/.test(url.hostname)) return;
  // La página: desde el celular al instante; se actualiza en segundo plano
  if (req.mode === 'navigate' || (url.origin === location.origin && /\/(index\.html)?$/.test(url.pathname))) {
    e.respondWith(caches.open(SHELL).then(async c => {
      const cached = await c.match('./');
      const net = fetch(req, { cache: 'no-store' }).then(r => { if (r.ok) c.put('./', r.clone()); return r; }).catch(() => null);
      if (cached) { e.waitUntil(net); return cached; }
      return (await net) || new Response('<h1>Sin conexión</h1><p>Abrí Góndola una vez con conexión para poder usarla sin señal.</p>', { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
    }));
    return;
  }
  // Catálogo SEPA (rama catalogo): desde el celular si ya se consultó, actualizándose en segundo plano
  if (url.hostname === 'raw.githubusercontent.com' && url.pathname.includes('/catalogo/')) {
    e.respondWith(caches.open(RUNTIME).then(async c => {
      const hit = await c.match(req);
      const net = fetch(req).then(r => { if (r.ok) c.put(req, r.clone()); return r; }).catch(() => null);
      if (hit) { e.waitUntil(net); return hit; }
      return (await net) || new Response('{}', { status: 504, headers: { 'Content-Type': 'application/json' } });
    }));
    return;
  }
  // Archivos propios, tipografías y librerías: primero el celular, si no la red (y se guarda)
  const own = url.origin === location.origin;
  const cdn = /fonts\.(googleapis|gstatic)\.com$|cdn\.jsdelivr\.net$|unpkg\.com$|cdnjs\.cloudflare\.com$/.test(url.hostname);
  if (!own && !cdn) return;
  e.respondWith(caches.match(req, { ignoreSearch: own }).then(hit => hit || fetch(req).then(r => {
    if (r.ok || r.type === 'opaque') { const cp = r.clone(); caches.open(own ? SHELL : RUNTIME).then(c => c.put(req, cp)); }
    return r;
  })));
});
