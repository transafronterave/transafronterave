# Panel de administración — guía rápida

**Dirección:** https://transafronterave.com/admin/ (privada: no aparece en Google y solo entra quien tenga permiso en GitHub).

## Qué puedes cambiar

| Sección del panel | Qué hace |
|---|---|
| **Ajustes de productos** | Busca un producto por su nombre y cámbiale: precio fijo en USD, precio «antes» (tachado), nombre, descripción corta, foto; ocúltalo; márcalo como ⭐ destacado o 🔥 oferta. Para volver a lo original, **borra el ajuste**. |
| **Productos propios** | Agrega productos que no están en el catálogo automático (nombre, categoría, precio USD, foto, descripción, peso). Desactiva «Visible en la tienda» para esconderlos sin borrarlos. |
| **Página de inicio** | Barra de anuncio de arriba, diapositivas del carrusel (título, subtítulo, botón, imagen, color), banner con imagen y enlace, y la lista ordenada de «Ofertas del día». |
| **WhatsApp y contacto** | Número de WhatsApp que usa **todo** el sitio (botones, carrito, guías), mensaje del botón Ayuda, ubicación, correo, redes y horario del pie de página. |

Al pulsar **Guardar**, el cambio queda guardado en GitHub y la web se actualiza sola en **2 a 4 minutos** (recarga la página para verlo).

### Bueno saber
- **Precios:** si no pones precio fijo, el producto sigue con el precio automático (se ajusta solo con la tasa del día). El precio fijo **no** cambia con la tasa.
- **Textos:** escribe siempre «Enviamos por MRW a toda Venezuela (costo aparte)». No prometas envío sin costo ni uses nombres de otras tiendas: el sistema rechaza esos textos y deja el original.
- **Fotos:** JPG, PNG o WebP de máximo 2,5 MB. Cuadradas para productos; horizontales (ej. 1600×400) para el banner.
- **Si algo no se publicó:** en GitHub → pestaña *Actions* → «Panel (publicar cambios)» aparece en rojo; abre el paso y busca las líneas `ERROR:`; dicen qué corregir.
- El catálogo automático se renueva todos los días; tus ajustes se vuelven a aplicar solos. Si un producto desaparece del catálogo, su ajuste queda marcado «⚠️ producto no encontrado» y puedes borrarlo.

## Cómo entrar (hoy: con token)

Necesitas:
1. **Una cuenta de GitHub** con permiso de escritura en el repositorio `transafronterave/transafronterave` (el administrador del repositorio te invita en *Settings → Collaborators*).
2. **Un token personal** de esa cuenta:
   - GitHub → foto de perfil → *Settings* → *Developer settings* → *Personal access tokens* → **Fine-grained tokens** → *Generate new token*.
   - *Repository access*: **Only select repositories** → `transafronterave/transafronterave`.
   - *Permissions → Repository permissions*: **Contents: Read and write** (Metadata: Read se agrega solo).
   - Elige una fecha de vencimiento (ej. 1 año) y copia el token (empieza por `github_pat_`).
3. Abre https://transafronterave.com/admin/ → **Iniciar sesión con un token de acceso** → pega el token. El navegador lo recuerda; para salir usa el ícono de perfil → *Cerrar sesión*.

> No compartas el token. Si se pierde o se filtra, bórralo en la misma página de GitHub y crea otro.

## Mejora opcional: botón «Iniciar sesión con GitHub» (sin token)

Para entrar solo con usuario y contraseña de GitHub hace falta un pequeño servicio de autenticación gratuito ([sveltia-cms-auth](https://github.com/sveltia/sveltia-cms-auth)) en Cloudflare Workers. No está creado; los pasos son:
1. En Cloudflare → *Workers & Pages* → desplegar `sveltia-cms-auth` (botón «Deploy to Cloudflare» de su página). Anota la URL, p. ej. `https://sveltia-cms-auth.<subdominio>.workers.dev`.
2. En GitHub → *Settings → Developer settings → OAuth Apps → New OAuth App*: Homepage `https://transafronterave.com`, Authorization callback URL `https://sveltia-cms-auth.<subdominio>.workers.dev/callback`. Copia Client ID y genera un Client Secret.
3. En el Worker → *Settings → Variables*: `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` (como secreto) y `ALLOWED_DOMAINS` = `transafronterave.com`.
4. En `admin/config.yml`, descomenta `base_url:` bajo `backend:` y pon la URL del Worker. Guardar y listo.

## Para el técnico
- Panel: `admin/index.html` + `admin/config.yml` (Sveltia CMS, backend GitHub, rama `main`).
- Datos que edita el panel: `data/ajustes_productos.json`, `data/productos_manuales.json`, `data/sitio/inicio.json`, `data/sitio/config.json`, imágenes en `img/subidas/`.
- `scripts/ajustes.py` aplica los ajustes al publicar `data/idx.json`, `data/c/*.json` y `catalogo_meta.csv` (`productos.json` sigue siendo el catálogo base sin ajustes). `scripts/sitio.py` escribe los bloques `<!--panel:…-->` de `index.html`. `scripts/panel.py` orquesta todo y lo ejecuta `.github/workflows/panel.yml` en cada guardado.
- Con los archivos del panel vacíos (`[]`), la salida es idéntica a la de antes.
