# Herramientas (/herramientas/) — PREPARADO, SIN PUBLICAR

Páginas: `/herramientas/` (índice), `calculadora/`, `encomienda/`, `plantilla/` (descarga .xlsx + pre-reserva por WhatsApp +58 412 0886940).
Tasas compartidas: `herramientas/tasas.js` (lo carga la calculadora) y `herramientas/tasas.json`.
Las páginas se generan con `/workspace/negocios/dolar-hoy/herramientas/web/integrar.py` (fuera del repo); editar allí y regenerar.

## Actualizar tasas a diario
Manual: `python3 scripts/tasas_herramientas.py` (solo librería estándar; si falta una tasa no sobrescribe nada).

Opción A — añadir un paso al workflow existente `.github/workflows/tasas.yml` (ya corre cada 30 min), NO aplicado:
```yaml
      - run: python3 scripts/tasas_herramientas.py || echo "tasas herramientas: sin cambios"
      # y en el `git add` agregar: herramientas/tasas.json herramientas/tasas.js
```
Opción B — cron en una máquina con el repo: `5 7 * * * cd /ruta/transafronterave && python3 scripts/tasas_herramientas.py && git add herramientas/tasas.* && git commit -m "Tasas herramientas" && git push`

## Cloudflare Web Analytics (sin cookies)
Cada página tiene un bloque con `var CF_TOKEN="";`. Vacío = no se carga nada. Al crear la cuenta, pegar el token en las 4 páginas
(o en `integrar.py` y regenerar). Alternativa sin tocar código: activar Web Analytics con proxy de Cloudflare si el DNS pasa por Cloudflare.

## Sitemap (entradas preparadas, NO añadidas a sitemap.xml)
```xml
  <url><loc>https://transafronterave.com/herramientas/</loc><lastmod>2026-11-04</lastmod></url>
  <url><loc>https://transafronterave.com/herramientas/calculadora/</loc><lastmod>2026-11-04</lastmod></url>
  <url><loc>https://transafronterave.com/herramientas/encomienda/</loc><lastmod>2026-11-04</lastmod></url>
  <url><loc>https://transafronterave.com/herramientas/plantilla/</loc><lastmod>2026-11-04</lastmod></url>
```
Pendiente opcional: enlace «Herramientas» en el menú de `/` y `/guias/` (lo generan scripts/sitio.py y scripts/guias.py; no se tocó).
Fuentes y supuestos de tarifas: archivo interno (no se publica).
