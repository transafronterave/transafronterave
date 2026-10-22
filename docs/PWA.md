# App instalable (PWA)

- `manifest.webmanifest` + íconos en `icons/` y `apple-touch-icon.png` (generados desde `logo-tf.png`).
- `sw.js`: HTML y datos (JSON/CSV/XML) **primero la red** (precios siempre al día; sin conexión usa la última copia); imágenes y estáticos **primero caché** (máx. 400 archivos); página `offline.html` si no hay conexión. `/admin/` nunca se intercepta ni se guarda.
- `pwa.js` (en todas las páginas públicas; `scripts/guias.py` lo incluye en las guías): registra el service worker y muestra el botón **📲 Instalar app** (Android/Chrome: instalación directa; iPhone: aviso «Compartir → Agregar a inicio»).
- Para forzar que todos reciban una versión nueva del service worker, cambia `V = "tf-v1"` en `sw.js`.

## Publicar en Google Play (opcional, no hecho)
1. Generar el paquete TWA con **PWABuilder** (pwabuilder.com → URL del sitio → Android) o **Bubblewrap** (`npx @bubblewrap/cli init --manifest https://transafronterave.com/manifest.webmanifest`). Paquete sugerido: `com.transafronterave.app`.
2. Guardar bien la llave de firma (keystore) que se genera.
3. Publicar `/.well-known/assetlinks.json` con el `package_name` y la huella SHA-256 de la llave (la de Play App Signing si se usa), para que la app abra sin barra del navegador. En GitHub Pages con Jekyll, la carpeta `.well-known` requiere `include: [".well-known"]` en `_config.yml`.
4. Cuenta de desarrollador de Google Play (pago único) → subir el `.aab`, ficha, capturas y política de privacidad.
