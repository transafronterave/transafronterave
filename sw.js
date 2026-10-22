/* Service worker de TRANSAFRONTERA VE.
   - HTML y datos (JSON/CSV/XML): primero la red (precios siempre al día); sin conexión, la última copia guardada.
   - Imágenes y archivos estáticos: primero la copia guardada, con límite de cantidad.
   - /admin/ queda fuera: nunca se intercepta ni se guarda. */
const V = "tf-v1", BASE = V + "-base", PAGES = V + "-paginas", ASSETS = V + "-estaticos", MAX_ASSETS = 400, MAX_PAGES = 60;
const PRECACHE = ["/offline.html", "/logo-tf.png", "/icons/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(BASE).then(c => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => !k.startsWith(V + "-")).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function trim(name, max) {
  const c = await caches.open(name), ks = await c.keys();
  for (let i = 0; i < ks.length - max; i++) await c.delete(ks[i]);
}

async function networkFirst(req, isNav) {
  const c = await caches.open(PAGES);
  try {
    const r = await fetch(isNav ? req : new Request(req, { cache: "no-cache" }));
    if (r.ok) { c.put(req, r.clone()); trim(PAGES, MAX_PAGES); }
    return r;
  } catch (err) {
    const hit = await c.match(req) || await c.match(req, { ignoreSearch: true });
    if (hit) return hit;
    if (isNav) return caches.match("/offline.html");
    throw err;
  }
}

async function cacheFirst(req) {
  const c = await caches.open(ASSETS), hit = await c.match(req) || await caches.match(req);
  if (hit) return hit;
  const r = await fetch(req);
  if (r.ok && r.type === "basic") { c.put(req, r.clone()); trim(ASSETS, MAX_ASSETS); }
  return r;
}

self.addEventListener("fetch", e => {
  const req = e.request;
  if (req.method !== "GET") return;
  const u = new URL(req.url);
  if (u.origin !== location.origin) return;                       // otros dominios: sin tocar
  if (u.pathname === "/admin" || u.pathname.startsWith("/admin/")) return;  // panel: nunca
  if (u.pathname === "/sw.js") return;
  const isNav = req.mode === "navigate";
  if (isNav || /\.(html?|json|csv|xml|txt|webmanifest)$/i.test(u.pathname) || u.pathname.endsWith("/")) {
    e.respondWith(networkFirst(req, isNav));
  } else if (/\.(png|jpe?g|webp|gif|svg|ico|avif|css|js|woff2?)$/i.test(u.pathname)) {
    e.respondWith(cacheFirst(req));
  }
});
